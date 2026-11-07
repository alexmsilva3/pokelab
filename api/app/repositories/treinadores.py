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

from app.game.trainers import StatusTreinador
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

    Sem `populate_existing` de proposito, ao contrario de
    `laboratorios_repo.travar` (auditoria da revisao da Fase 7): nenhuma
    dependencia de rota pre-carrega um `Treinador` antes do servico pedir o
    lock — `professor_atual` so toca `Professor` e `Laboratorio` — entao este
    `SELECT` e sempre a primeira vez que ESTE registro entra no identity map
    da sessao da requisicao. Nao ha leitura antiga para o lock deixar intocada.
    """
    return sessao.scalar(
        select(Treinador)
        .where(Treinador.laboratorio_id == laboratorio_id, Treinador.id == treinador_id)
        .with_for_update()
    )


def travar_treinador_com_time(
    sessao: Session, laboratorio_id: uuid.UUID, treinador_id: uuid.UUID
) -> Treinador | None:
    """Trava o treinador e carrega o time, para quem precisa do poder sob lock (spec 006).

    `with_for_update()` recai sobre a consulta principal de `Treinador`; o
    time continua vindo por `selectinload` — uma segunda consulta, sem join —
    entao a trava nunca encosta num `PokemonInstancia`, so no treinador. E o
    que basta: o despacho so precisa impedir que ESTE treinador va para duas
    expedicoes ao mesmo tempo, nao congelar o time dele.

    Sem `populate_existing`: mesmo raciocinio de `travar_treinador` acima —
    nada pre-carrega este `Treinador` antes do despacho ou do `claim`
    chamarem esta funcao, entao nao ha objeto obsoleto no identity map para
    `with_for_update()` deixar de atualizar.
    """
    consulta = _com_time_e_especie(
        select(Treinador).where(
            Treinador.laboratorio_id == laboratorio_id, Treinador.id == treinador_id
        )
    ).with_for_update()
    return sessao.scalars(consulta).unique().one_or_none()


def atualizar_status(treinador: Treinador, status: StatusTreinador) -> None:
    """Grava o novo status do treinador (ocupado ao despachar, livre ao voltar ou abortar)."""
    treinador.status = status.value


def concluir_expedicao(treinador: Treinador, *, nivel: int, experiencia: int) -> None:
    """Fecha o ciclo da expedicao (regra 20 da spec 007): libera o treinador,
    grava a progressao que `game.trainers` ja calculou e soma mais uma
    expedicao concluida ao historico dele."""
    treinador.status = StatusTreinador.DISPONIVEL.value
    treinador.nivel = nivel
    treinador.experiencia = experiencia
    treinador.expedicoes_concluidas += 1


def despachar_para_entrega(treinador: Treinador) -> None:
    """Poe o treinador EM_ENTREGA (regra 20 da spec 008, aceite)."""
    treinador.status = StatusTreinador.EM_ENTREGA.value


def concluir_entrega(treinador: Treinador, *, nivel: int, experiencia: int) -> None:
    """Fecha o ciclo da entrega (criterio 26 da spec 008): libera o
    treinador, grava a progressao que `game.trainers` ja calculou e soma mais
    uma entrega concluida ao historico dele. Mesmo papel de
    `concluir_expedicao`, para o segundo uso do treinador."""
    treinador.status = StatusTreinador.DISPONIVEL.value
    treinador.nivel = nivel
    treinador.experiencia = experiencia
    treinador.entregas_concluidas += 1


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

    Sem `populate_existing`, pelo mesmo motivo de `travar_treinador`: nenhum
    `PokemonInstancia` chega pre-carregado na sessao da requisicao antes desta
    chamada (a previa, que leria sem lock, e sempre uma requisicao separada).
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
