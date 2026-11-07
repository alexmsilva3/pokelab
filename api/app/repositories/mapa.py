"""Leitura do grafo de locais e do progresso de um laboratorio sobre ele.

Duas consultas alimentam o mapa inteiro — os dez locais e os visitados do
laboratorio — nunca uma por local (plan.md da spec 005): `GET /map` chama
`listar_locais` e `listar_visitados` uma vez cada, e passa o resultado para
`app.game.mapa`, que roda o Dijkstra uma unica vez para a tela toda.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, joinedload

from app.models import Local, LocalDesbloqueado, LocalEncontro, PokedexAvistamento, PokemonEspecie


def listar_locais(sessao: Session) -> list[Local]:
    """Os dez locais do seed (Artigo V), em qualquer ordem estavel.

    A ordenacao que importa para a tela e por distancia, e essa e
    responsabilidade de `app.game.mapa.visao_do_mapa` — este repositorio so
    devolve o acervo.
    """
    return list(sessao.scalars(select(Local).order_by(Local.id)))


def listar_visitados(sessao: Session, laboratorio_id: uuid.UUID) -> set[str]:
    """Os ids dos locais que este laboratorio ja desbloqueou."""
    return set(
        sessao.scalars(
            select(LocalDesbloqueado.local_id).where(
                LocalDesbloqueado.laboratorio_id == laboratorio_id
            )
        )
    )


def buscar_linhas_de_encontro(sessao: Session, local_id: str) -> list[LocalEncontro]:
    """A tabela de encontros de um local, na ordem canonica (spec 007).

    `especie_id` crescente: a ordem das linhas e parte do resultado do
    sorteio por peso (Artigo III), e `ContextoDeResolucao` exige que a tabela
    chegue assim. O `ORDER BY` aqui e a garantia — nunca iterar um `dict` nem
    um `set` montado em runtime para alimentar o sorteio.
    """
    return list(
        sessao.scalars(
            select(LocalEncontro)
            .where(LocalEncontro.local_id == local_id)
            .order_by(LocalEncontro.especie_id)
        )
    )


def listar_todos_os_encontros(sessao: Session) -> list[LocalEncontro]:
    """Toda a tabela `local_encontros`, de qualquer local (Fase 8, spec 008).

    O gerador de entregas precisa saber ONDE cada especie candidata aparece
    para aplicar o filtro de alcancavel (`game.delivery.candidatas_do_nivel`):
    uma consulta so, em vez de uma por especie ou uma por local — o catalogo
    inteiro de encontros nunca passa de algumas centenas de linhas no seed da
    v1 (dez locais).
    """
    return list(sessao.scalars(select(LocalEncontro).order_by(LocalEncontro.especie_id)))


def desbloquear(
    sessao: Session, laboratorio_id: uuid.UUID, local_id: str, desbloqueado_em: datetime
) -> bool:
    """Marca o destino como desbloqueado; idempotente (regra 18, criterio 5).

    `ON CONFLICT DO NOTHING` em vez de ler-depois-escrever: a mesma expedicao
    resolvida duas vezes, ou duas resolucoes concorrentes do mesmo
    laboratorio desbloqueando o mesmo local, nao duplicam a linha nem pisam
    uma na outra. O booleano devolvido diz se ESTA chamada foi quem
    desbloqueou — falso quando o destino ja estava aberto antes, que e o que
    `relatorio.local_desbloqueado` precisa para nao anunciar uma novidade que
    nao e.
    """
    instrucao = (
        pg_insert(LocalDesbloqueado)
        .values(laboratorio_id=laboratorio_id, local_id=local_id, desbloqueado_em=desbloqueado_em)
        .on_conflict_do_nothing(
            index_elements=[LocalDesbloqueado.laboratorio_id, LocalDesbloqueado.local_id]
        )
        .returning(LocalDesbloqueado.local_id)
    )
    resultado = sessao.execute(instrucao)
    return resultado.first() is not None


@dataclass(frozen=True, slots=True)
class LinhaDeAvistamento:
    """Uma especie avistada por este laboratorio neste local, ja combinada."""

    especie: PokemonEspecie
    vezes_visto: int
    primeiro_visto_em: datetime


def listar_avistamentos(
    sessao: Session, laboratorio_id: uuid.UUID, local_id: str
) -> list[LinhaDeAvistamento]:
    """As especies que os treinadores deste laboratorio ja viram neste local.

    Filtra por laboratorio **e** local (regra 9 da spec 005): um laboratorio
    nunca ve o que avistou em outro lugar, nem o que outro laboratorio avistou
    aqui. Local nunca visitado por este laboratorio devolve lista vazia, sem
    consulta extra nem caso especial — e exatamente o que a ausencia de linhas
    em `pokedex_avistamentos` ja significa.
    """
    avistamentos = sessao.scalars(
        select(PokedexAvistamento)
        .where(
            PokedexAvistamento.laboratorio_id == laboratorio_id,
            PokedexAvistamento.local_id == local_id,
        )
        .options(joinedload(PokedexAvistamento.especie))
        .order_by(PokedexAvistamento.especie_id)
    )
    return [
        LinhaDeAvistamento(
            especie=avistamento.especie,
            vezes_visto=avistamento.vezes_visto,
            primeiro_visto_em=avistamento.primeiro_visto_em,
        )
        for avistamento in avistamentos
    ]
