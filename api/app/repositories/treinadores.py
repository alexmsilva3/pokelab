"""Acesso a tabela `treinadores` e, por tabela, ao time que cada um carrega.

O risco do plan.md da spec 004 e o mesmo de `repositories/pokemon.py`: o time
tem ate tres Pokemon, cada um com sua especie, e tres treinadores com time
cheio sao nove Pokemon e nove especies. `Treinador.time` (o lado inverso de
`PokemonInstancia.treinador_id`, acrescentado em `models/estado.py` sem
migracao nenhuma) deixa resolver isso com `selectinload`/`joinedload` em vez de
uma consulta por treinador.

A escrita do time precisa de duas travas na mesma transacao (Artigo VII): a
linha do treinador, para que dois `PUT` no MESMO treinador nao se pisem, e as
linhas dos Pokemon envolvidos, para que dois `PUT` em treinadores DIFERENTES
nao atribuam o mesmo Pokemon aos dois. `travar_pokemon_envolvidos` ordena por
`id` de proposito: duas transacoes que pedem os mesmos Pokemon em ordens
diferentes travando sem ordem fixa e a receita classica de deadlock.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import PokemonInstancia, Treinador


def _com_time_e_especie(consulta: Select) -> Select:
    return consulta.options(selectinload(Treinador.time).joinedload(PokemonInstancia.especie))


def listar(sessao: Session, laboratorio_id: uuid.UUID) -> list[Treinador]:
    """Os treinadores do laboratorio, ordenados de forma estavel.

    Sem paginacao de proposito: o laboratorio tem exatamente tres (plan.md).
    """
    consulta = _com_time_e_especie(
        select(Treinador).where(Treinador.laboratorio_id == laboratorio_id)
    ).order_by(Treinador.id)
    return list(sessao.scalars(consulta))


def buscar_por_id(
    sessao: Session, laboratorio_id: uuid.UUID, treinador_id: uuid.UUID
) -> Treinador | None:
    """O treinador so com as colunas proprias, sem o time.

    Para quem precisa apenas do nivel — caso de `GET /map/{id}?treinador_id=`,
    que estima a duracao da ida — carregar o time e a especie de cada membro
    seria trabalho que ninguem le. Escopado ao laboratorio, como sempre:
    um id de outro laboratorio nao existe para quem pergunta (404, nunca 403).
    """
    return sessao.scalar(
        select(Treinador).where(
            Treinador.laboratorio_id == laboratorio_id, Treinador.id == treinador_id
        )
    )


def buscar_detalhe(
    sessao: Session, laboratorio_id: uuid.UUID, treinador_id: uuid.UUID
) -> Treinador | None:
    """Um treinador do laboratorio, com o time e a especie de cada membro.

    Filtra por `laboratorio_id` na propria consulta: um id de outro
    laboratorio nunca chega a existir para quem pergunta (404, nunca 403).
    """
    consulta = _com_time_e_especie(
        select(Treinador).where(
            Treinador.laboratorio_id == laboratorio_id, Treinador.id == treinador_id
        )
    )
    return sessao.scalars(consulta).unique().one_or_none()


def travar_treinador(
    sessao: Session, laboratorio_id: uuid.UUID, treinador_id: uuid.UUID
) -> Treinador | None:
    """Trava a linha do treinador ate o fim da transacao (Artigo VII).

    So a linha do treinador, sem o time: quem precisa dos Pokemon travados
    tambem chama `travar_pokemon_envolvidos` na mesma transacao.
    """
    return sessao.scalar(
        select(Treinador)
        .where(Treinador.laboratorio_id == laboratorio_id, Treinador.id == treinador_id)
        .with_for_update()
    )


def _pokemon_envolvidos(
    laboratorio_id: uuid.UUID, treinador_id: uuid.UUID, pokemon_ids: Sequence[uuid.UUID]
) -> Select:
    """Os Pokemon que uma troca de time pode tocar.

    E a uniao de quem foi pedido (para descobrir se esta livre, com outro
    treinador, ou comprometido) com quem ja esta no time hoje (para saber quem
    sai quando nao foi pedido de novo). Escopado ao laboratorio: um id de
    outro laboratorio nunca aparece aqui, e vira `PokemonDesconhecido` no
    dominio sem que este repositorio precise saber por que.
    """
    return (
        select(PokemonInstancia)
        .where(
            PokemonInstancia.laboratorio_id == laboratorio_id,
            (PokemonInstancia.id.in_(pokemon_ids))
            | (PokemonInstancia.treinador_id == treinador_id),
        )
        .order_by(PokemonInstancia.id)
    )


def buscar_pokemon_envolvidos(
    sessao: Session,
    laboratorio_id: uuid.UUID,
    treinador_id: uuid.UUID,
    pokemon_ids: Sequence[uuid.UUID],
) -> list[PokemonInstancia]:
    """Leitura sem trava, para a previa: ela nao grava, entao nao precisa travar."""
    consulta = _pokemon_envolvidos(laboratorio_id, treinador_id, pokemon_ids).options(
        joinedload(PokemonInstancia.especie)
    )
    return list(sessao.scalars(consulta).unique())


def travar_pokemon_envolvidos(
    sessao: Session,
    laboratorio_id: uuid.UUID,
    treinador_id: uuid.UUID,
    pokemon_ids: Sequence[uuid.UUID],
) -> list[PokemonInstancia]:
    """`SELECT ... FOR UPDATE` nas linhas que o salvamento pode escrever.

    Sem esta trava, dois `PUT` concorrentes em treinadores diferentes podem
    ler o mesmo Pokemon como livre antes de qualquer um dos dois gravar, e os
    dois o atribuem. Com a trava, o segundo bloqueia ate o primeiro terminar e
    enxerga o `treinador_id` ja gravado por ele.
    """
    consulta = _pokemon_envolvidos(laboratorio_id, treinador_id, pokemon_ids).with_for_update()
    return list(sessao.scalars(consulta))


def aplicar_time(
    pokemon_por_id: dict[uuid.UUID, PokemonInstancia],
    *,
    treinador_id: uuid.UUID,
    para_adicionar: Sequence[uuid.UUID],
    para_remover: Sequence[uuid.UUID],
) -> None:
    """Grava a substituicao total que `game.team.validar_time` ja aprovou."""
    for pokemon_id in para_adicionar:
        pokemon_por_id[pokemon_id].treinador_id = treinador_id
    for pokemon_id in para_remover:
        pokemon_por_id[pokemon_id].treinador_id = None
