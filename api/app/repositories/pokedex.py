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
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.game.expedition import AvistamentoEmCampo
from app.models import PokedexAvistamento, PokedexEntrada, PokemonEspecie, PokemonInstancia


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


def buscar_vistas(sessao: Session, laboratorio_id: uuid.UUID) -> set[int]:
    """As especies que este laboratorio ja viu, para `ContextoDeResolucao.especies_vistas`.

    So `visto`, nunca `capturado`: o criterio 17/18 da spec 007 fala em
    DESCOBERTA na primeira vez que a especie e ENFRENTADA, nao capturada.

    Chamada em `despachar()`, NUNCA em `claim()` (achado 3 da revisao da Fase
    7): o resultado vira `Expedicao.especies_vistas_no_envio`, o retrato que o
    invariante 19 exige. Uma leitura no `claim` seria ao vivo e fora de lock —
    exatamente o que permitia a dois `claim`s concorrentes do mesmo
    laboratorio anunciarem DESCOBERTA da mesma especie.
    """
    return set(
        sessao.scalars(
            select(PokedexEntrada.especie_id).where(
                PokedexEntrada.laboratorio_id == laboratorio_id,
                PokedexEntrada.visto.is_(True),
            )
        )
    )


def registrar_avistamentos(
    sessao: Session,
    laboratorio_id: uuid.UUID,
    local_id: str,
    avistamentos: Sequence[AvistamentoEmCampo],
    especies_capturadas: set[int],
    agora: datetime,
) -> None:
    """Descarrega na Pokedex o que a expedicao enfrentou (SDD 4.8, regra 12).

    Dois UPSERTs por especie, ambos idempotentes: `PokedexEntrada` marca
    `visto` (e `capturado`, se foi o caso desta expedicao) sem nunca
    RETROCEDER um `capturado` ja verdadeiro de uma captura anterior — por
    isso o `SET` usa `OR` com o valor atual em vez de sobrescrever.
    `PokedexAvistamento` soma `vezes_visto`, porque a mesma especie pode
    aparecer varias vezes no mesmo relatorio e em relatorios anteriores.
    """
    for avistamento in avistamentos:
        capturou_agora = avistamento.especie_id in especies_capturadas

        entrada = pg_insert(PokedexEntrada).values(
            laboratorio_id=laboratorio_id,
            especie_id=avistamento.especie_id,
            visto=True,
            capturado=capturou_agora,
            primeiro_visto_em=agora,
        )
        sessao.execute(
            entrada.on_conflict_do_update(
                index_elements=[PokedexEntrada.laboratorio_id, PokedexEntrada.especie_id],
                set_={
                    "visto": True,
                    "capturado": PokedexEntrada.capturado | entrada.excluded.capturado,
                },
            )
        )

        avistamento_stmt = pg_insert(PokedexAvistamento).values(
            laboratorio_id=laboratorio_id,
            especie_id=avistamento.especie_id,
            local_id=local_id,
            primeiro_visto_em=agora,
            vezes_visto=avistamento.vezes,
        )
        sessao.execute(
            avistamento_stmt.on_conflict_do_update(
                index_elements=[
                    PokedexAvistamento.laboratorio_id,
                    PokedexAvistamento.especie_id,
                    PokedexAvistamento.local_id,
                ],
                set_={
                    "vezes_visto": PokedexAvistamento.vezes_visto
                    + avistamento_stmt.excluded.vezes_visto
                },
            )
        )
