"""Contrato de `GET /ranch` (spec 008, plan.md).

So leitura: nenhuma linha muda com esta chamada. `items` reusa `PokemonResumo`
de `schemas/pokemon.py` — e a mesma ficha resumida de `GET /pokemon`, e o
viveiro nao precisa de um segundo formato para o mesmo Pokemon.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.schemas.pokemon import PokemonResumo


class EstadoDoViveiroLer(BaseModel):
    """Os quatro numeros de `game.viveiro.EstadoDoViveiro`, mais os itens.

    `lugares_faltando` e sempre zero quando `transbordado` e falso — inclusive
    com o viveiro exatamente cheio (criterio 1, regra 2 da spec 008).
    """

    capacidade: int
    ocupacao: int
    transbordado: bool
    lugares_faltando: int
    items: list[PokemonResumo]
