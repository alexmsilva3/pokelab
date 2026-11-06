"""Rotas do acervo de Pokemon do laboratorio (spec 003): listagem, ficha e apelido."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencias import SessaoProfessor, professor_atual
from app.game import balance
from app.repositories.pokemon import PAGE_SIZE_PADRAO, FiltrosPokemon
from app.schemas.pokemon import ApelidoAtualizar, PaginaPokemon, PokemonDetalhe
from app.services import pokemon as pokemon_service

router = APIRouter(prefix="/pokemon", tags=["pokemon"])

# Os dezoito tipos de Pokemon (plan.md). `tipo` so aceita um deles; qualquer
# outro valor e entrada invalida (422), nao um filtro que silenciosamente
# devolve lista vazia.
TipoPokemon = Literal[
    "normal",
    "fire",
    "water",
    "electric",
    "grass",
    "ice",
    "fighting",
    "poison",
    "ground",
    "flying",
    "psychic",
    "bug",
    "rock",
    "ghost",
    "dragon",
    "dark",
    "steel",
    "fairy",
]


# O offset e calculado em Python como (page - 1) * page_size. Sem teto, uma
# pagina absurda estourava o bigint do OFFSET do Postgres e virava 500 com
# corpo de texto puro, fora do envelope da aplicacao. Nenhum acervo real chega
# perto disto, entao recusar e melhor que paginar o infinito.
PAGE_MAXIMA = 1_000_000


@router.get("", response_model=PaginaPokemon)
def listar_pokemon(
    tipo: TipoPokemon | None = None,
    nivel_min: int | None = Query(default=None, ge=1, le=balance.NIVEL_MAXIMO),
    nivel_max: int | None = Query(default=None, ge=1, le=balance.NIVEL_MAXIMO),
    atribuido: bool | None = None,
    livre: bool | None = None,
    page: int = Query(default=1, ge=1, le=PAGE_MAXIMA),
    # Sem `le` aqui de proposito: o teto e cortado em silencio no servico
    # (plan.md), nao recusado com 422.
    page_size: int = Query(default=PAGE_SIZE_PADRAO, ge=1),
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> PaginaPokemon:
    filtros = FiltrosPokemon(
        tipo=tipo, nivel_min=nivel_min, nivel_max=nivel_max, atribuido=atribuido, livre=livre
    )
    return pokemon_service.listar(
        sessao, sessao_professor.laboratorio.id, filtros, page=page, page_size=page_size
    )


@router.get("/{pokemon_id}", response_model=PokemonDetalhe)
def obter_pokemon(
    pokemon_id: uuid.UUID,
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> PokemonDetalhe:
    return pokemon_service.obter_detalhe(sessao, sessao_professor.laboratorio.id, pokemon_id)


@router.patch("/{pokemon_id}", response_model=PokemonDetalhe)
def renomear_pokemon(
    pokemon_id: uuid.UUID,
    dados: ApelidoAtualizar,
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> PokemonDetalhe:
    return pokemon_service.atualizar_apelido(
        sessao, sessao_professor.laboratorio.id, pokemon_id, dados.apelido
    )
