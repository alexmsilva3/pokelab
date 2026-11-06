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
from sqlalchemy.orm import Session, joinedload

from app.models import Local, LocalDesbloqueado, PokedexAvistamento, PokemonEspecie


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
