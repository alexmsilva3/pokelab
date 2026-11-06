"""Acesso as 151 entradas da Pokedex de um laboratorio (spec 003).

A Pokedex sempre lista as 151 especies (regra 8), qualquer que seja o
progresso. Por isso a consulta parte de `pokemon_especies` com um LEFT JOIN em
`pokedex_entradas`: uma especie sem linha de progresso e "desconhecida", nao
um item ausente da resposta.

Duas consultas, nao cento e cinquenta e uma: a contagem por especie vem de um
`GROUP BY` separado, nao de uma consulta por linha da Pokedex.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import PokedexEntrada, PokemonEspecie, PokemonInstancia


@dataclass(frozen=True, slots=True)
class LinhaPokedex:
    """Uma especie mais o progresso do laboratorio sobre ela, ja combinados.

    `visto`/`capturado` saem `False` quando a especie nunca apareceu no
    laboratorio (ausencia de linha em `pokedex_entradas`), nunca `None`: o
    chamador nao precisa saber distinguir "nunca visto" de "linha nula".
    """

    especie: PokemonEspecie
    visto: bool
    capturado: bool
    quantidade: int


def listar_entradas(sessao: Session, laboratorio_id: uuid.UUID) -> list[LinhaPokedex]:
    linhas = sessao.execute(
        select(PokemonEspecie, PokedexEntrada.visto, PokedexEntrada.capturado)
        .join(
            PokedexEntrada,
            and_(
                PokedexEntrada.especie_id == PokemonEspecie.id,
                PokedexEntrada.laboratorio_id == laboratorio_id,
            ),
            isouter=True,
        )
        .order_by(PokemonEspecie.id)
    ).all()

    contagens = dict(
        sessao.execute(
            select(PokemonInstancia.especie_id, func.count())
            .where(PokemonInstancia.laboratorio_id == laboratorio_id)
            .group_by(PokemonInstancia.especie_id)
        ).all()
    )

    return [
        LinhaPokedex(
            especie=especie,
            visto=bool(visto),
            capturado=bool(capturado),
            quantidade=contagens.get(especie.id, 0),
        )
        for especie, visto, capturado in linhas
    ]
