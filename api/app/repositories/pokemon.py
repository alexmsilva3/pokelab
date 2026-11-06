"""Acesso a tabela `pokemon_instancias` (spec 003).

A listagem precisa do nome, dos tipos e do sprite, que moram em
`pokemon_especies`. O risco e N+1: uma consulta por pagina viraria uma
consulta por Pokemon se a especie fosse buscada lazy, uma por item. O `join`
mais `contains_eager` abaixo resolve os dois problemas com a MESMA consulta —
filtrar por tipo e preencher `PokemonInstancia.especie` sem round-trip extra.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.models import PokemonEspecie, PokemonInstancia

PAGE_SIZE_PADRAO = 20
# Teto de protecao, nao regra de negocio: pedido acima disso e cortado em
# silencio (plan.md), nunca recusado.
# Teto de pagina. O router ja recusa acima disto com 422; aqui e a segunda
# linha de defesa, para que nenhum outro chamador estoure o OFFSET do Postgres.
PAGE_MAXIMA = 1_000_000
PAGE_SIZE_MAXIMO = 100


@dataclass(frozen=True, slots=True)
class FiltrosPokemon:
    """Os filtros combinaveis de `GET /pokemon`.

    `atribuido` e booleano de tres estados: `None` nao filtra, `True` traz so
    quem tem treinador, `False` so quem esta livre no laboratorio.
    """

    tipo: str | None = None
    nivel_min: int | None = None
    nivel_max: int | None = None
    atribuido: bool | None = None


def _condicoes(laboratorio_id: uuid.UUID, filtros: FiltrosPokemon) -> list:
    condicoes: list = [PokemonInstancia.laboratorio_id == laboratorio_id]

    if filtros.tipo is not None:
        # "casa com primario OU secundario" (plan.md) — um dos dois basta.
        condicoes.append(
            (PokemonEspecie.tipo_primario == filtros.tipo)
            | (PokemonEspecie.tipo_secundario == filtros.tipo)
        )
    if filtros.nivel_min is not None:
        condicoes.append(PokemonInstancia.nivel >= filtros.nivel_min)
    if filtros.nivel_max is not None:
        condicoes.append(PokemonInstancia.nivel <= filtros.nivel_max)
    if filtros.atribuido is True:
        condicoes.append(PokemonInstancia.treinador_id.is_not(None))
    elif filtros.atribuido is False:
        condicoes.append(PokemonInstancia.treinador_id.is_(None))

    return condicoes


def _query_juntada(laboratorio_id: uuid.UUID, filtros: FiltrosPokemon) -> Select:
    """Um unico join com a especie, usado tanto para filtrar quanto para contar."""
    return (
        select(PokemonInstancia)
        .join(PokemonInstancia.especie)
        .where(*_condicoes(laboratorio_id, filtros))
    )


def listar(
    sessao: Session,
    laboratorio_id: uuid.UUID,
    filtros: FiltrosPokemon,
    *,
    page: int,
    page_size: int,
) -> tuple[list[PokemonInstancia], int, int, int]:
    """Devolve a pagina, o total, e `page`/`page_size` ja normalizados.

    Ordenacao deterministica com desempate por `id`: sem isso o Postgres pode
    devolver a mesma linha em duas paginas diferentes, ou pular uma, quando
    duas linhas empatam no criterio principal.

    Devolve exatamente DUAS consultas, qualquer que seja o tamanho da pagina:
    uma de contagem, uma de dados com a especie ja junta via `contains_eager`.
    """
    page = min(max(page, 1), PAGE_MAXIMA)
    page_size = min(max(page_size, 1), PAGE_SIZE_MAXIMO)

    total = (
        sessao.scalar(
            select(func.count()).select_from(_query_juntada(laboratorio_id, filtros).subquery())
        )
        or 0
    )

    itens = list(
        sessao.scalars(
            _query_juntada(laboratorio_id, filtros)
            .options(contains_eager(PokemonInstancia.especie))
            .order_by(PokemonInstancia.nivel.desc(), PokemonInstancia.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )

    return itens, total, page, page_size


def buscar_detalhe(
    sessao: Session, laboratorio_id: uuid.UUID, pokemon_id: uuid.UUID
) -> PokemonInstancia | None:
    """Um Pokemon do laboratorio, com especie, treinador e local de captura.

    Filtra por `laboratorio_id` na propria consulta: um id de outro
    laboratorio nunca chega a existir para quem pergunta (404, nunca 403).
    """
    return sessao.scalar(
        select(PokemonInstancia)
        .where(
            PokemonInstancia.laboratorio_id == laboratorio_id,
            PokemonInstancia.id == pokemon_id,
        )
        .options(
            joinedload(PokemonInstancia.especie),
            joinedload(PokemonInstancia.treinador),
            joinedload(PokemonInstancia.local_captura),
        )
    )


def atualizar_apelido(pokemon: PokemonInstancia, apelido: str | None) -> None:
    pokemon.apelido = apelido
