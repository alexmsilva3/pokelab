"""Leitura das especies de referencia que o servico de registro precisa.

Esta busca e a fronteira que converte `PokemonEspecie` (modelo ORM) em
`EspecieInicial` (dataclass de `app.game.kit_inicial`), para que o Artigo I
nao seja atravessado por um objeto SQLAlchemy.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.game import balance
from app.models import PokemonEspecie


def buscar_iniciais(sessao: Session) -> list[PokemonEspecie]:
    """As especies dos tres starters declarados em `balance.STARTER_SPECIES_IDS`."""
    return list(
        sessao.scalars(
            select(PokemonEspecie).where(PokemonEspecie.id.in_(balance.STARTER_SPECIES_IDS))
        )
    )
