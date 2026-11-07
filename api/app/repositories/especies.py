"""Leitura das especies de referencia que o servico de registro precisa.

Esta busca e a fronteira que converte `PokemonEspecie` (modelo ORM) em
`EspecieInicial` (dataclass de `app.game.kit_inicial`), para que o Artigo I
nao seja atravessado por um objeto SQLAlchemy.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.game import balance
from app.models import PokemonEspecie

# Teto de seguranca do laco de `buscar_catalogo`: bem acima de qualquer
# cadeia de evolucao real (a maior de Kanto tem duas etapas), so para nunca
# girar para sempre se um dia o seed tiver um ciclo de `evolui_para_id`.
_VOLTAS_MAXIMAS_DO_CATALOGO = 200


def buscar_iniciais(sessao: Session) -> list[PokemonEspecie]:
    """As especies dos tres starters declarados em `balance.STARTER_SPECIES_IDS`."""
    return list(
        sessao.scalars(
            select(PokemonEspecie).where(PokemonEspecie.id.in_(balance.STARTER_SPECIES_IDS))
        )
    )


def listar_todas(sessao: Session) -> list[PokemonEspecie]:
    """As 151 especies do seed, em qualquer ordem estavel (Fase 8, spec 008).

    O gerador de entregas (`game.delivery.candidatas_do_nivel`) precisa do
    catalogo inteiro para montar a banda de raridade: a Pokedex do laboratorio
    NAO participa do filtro (SDD 4.9), entao nao ha WHERE por laboratorio
    aqui — e a mesma tabela de referencia para qualquer professor.
    """
    return list(sessao.scalars(select(PokemonEspecie).order_by(PokemonEspecie.id)))


def buscar_catalogo(sessao: Session, especie_ids: Iterable[int]) -> dict[int, PokemonEspecie]:
    """As especies pedidas MAIS toda a cadeia de evolucao delas (spec 007).

    `ContextoDeResolucao` recusa um catalogo parcial na propria construcao
    (Artigo VI): toda especie do time, toda especie da tabela de encontros e
    todo elo de evolucao delas precisa estar presente, ou a resolucao levanta
    `ContextoInvalido` antes de qualquer escrita. Este laco persegue
    `evolui_para_id` ate estabilizar, e nao assume quantas etapas a cadeia
    tem — ele nao depende do seed de Kanto ter no maximo duas.
    """
    pendentes = set(especie_ids)
    catalogo: dict[int, PokemonEspecie] = {}
    for _ in range(_VOLTAS_MAXIMAS_DO_CATALOGO):
        faltantes = pendentes - catalogo.keys()
        if not faltantes:
            break
        novas = sessao.scalars(select(PokemonEspecie).where(PokemonEspecie.id.in_(faltantes)))
        for especie in novas:
            catalogo[especie.id] = especie
            if especie.evolui_para_id is not None:
                pendentes.add(especie.evolui_para_id)
    return catalogo
