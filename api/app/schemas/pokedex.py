"""Contrato de `GET /pokedex` (spec 003).

A forma da entrada VARIA de proposito conforme o estado (plan.md): o nome de
uma especie nunca vista nao pode estar no corpo da resposta (regra 9,
criterio 9) — nem como campo nulo, porque o cliente ainda assim o
remonta no devtools, mas sim porque o campo nao existe nesta classe. O
discriminador `estado` e quem decide, por professor e por especie, qual das
tres classes abaixo o Pydantic usa para serializar a linha.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# --- Saida ---------------------------------------------------------------


class EntradaPokedexDesconhecida(BaseModel):
    numero: int
    estado: Literal["DESCONHECIDA"] = "DESCONHECIDA"


class EntradaPokedexVista(BaseModel):
    numero: int
    estado: Literal["VISTA"] = "VISTA"
    nome: str
    tipos: list[str]
    sprite: str


class EntradaPokedexCapturada(BaseModel):
    numero: int
    estado: Literal["CAPTURADA"] = "CAPTURADA"
    nome: str
    tipos: list[str]
    sprite: str
    quantidade: int


EntradaPokedex = Annotated[
    EntradaPokedexDesconhecida | EntradaPokedexVista | EntradaPokedexCapturada,
    Field(discriminator="estado"),
]


class PokedexLer(BaseModel):
    items: list[EntradaPokedex]
    capturadas: int
    vistas: int
