"""Contagens do cabecalho da tela do laboratorio.

`GET /me` precisa de quantos Pokemon, treinadores, locais e especies o
laboratorio tem, sem disparar uma consulta por numero. As cinco contagens
viram subconsultas escalares de um unico SELECT.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LocalDesbloqueado, PokedexEntrada, PokemonInstancia, Treinador


@dataclass(frozen=True, slots=True)
class ResumoLaboratorio:
    pokemon: int
    treinadores: int
    locais_desbloqueados: int
    especies_vistas: int
    especies_capturadas: int
    # Tarefa 9 da spec 008 (criterios 1 e 2): a ocupacao do viveiro tambem
    # aparece no resumo do `GET /me`, nao so no `GET /ranch` dedicado — mesma
    # contagem de `pokemon_repo.contar_viveiro`/`game.viveiro.ocupacao`
    # (Pokemon com `treinador_id` nulo), so que encaixada nesta MESMA
    # consulta para nao custar uma ida a mais ao banco.
    ocupacao_viveiro: int


def _contagem(modelo, laboratorio_id: uuid.UUID, *condicoes):
    return (
        select(func.count())
        .select_from(modelo)
        .where(modelo.laboratorio_id == laboratorio_id, *condicoes)
        .scalar_subquery()
    )


def contar(sessao: Session, laboratorio_id: uuid.UUID) -> ResumoLaboratorio:
    """As contagens do laboratorio, numa unica ida ao banco."""
    linha = sessao.execute(
        select(
            _contagem(PokemonInstancia, laboratorio_id),
            _contagem(Treinador, laboratorio_id),
            _contagem(LocalDesbloqueado, laboratorio_id),
            _contagem(PokedexEntrada, laboratorio_id, PokedexEntrada.visto.is_(True)),
            _contagem(PokedexEntrada, laboratorio_id, PokedexEntrada.capturado.is_(True)),
            _contagem(PokemonInstancia, laboratorio_id, PokemonInstancia.treinador_id.is_(None)),
        )
    ).one()
    return ResumoLaboratorio(
        pokemon=linha[0],
        treinadores=linha[1],
        locais_desbloqueados=linha[2],
        especies_vistas=linha[3],
        especies_capturadas=linha[4],
        ocupacao_viveiro=linha[5],
    )
