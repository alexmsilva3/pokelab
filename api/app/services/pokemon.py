"""Caso de uso do acervo de Pokemon do laboratorio (spec 003).

Fase so de leitura, exceto o apelido. A fronteira do Artigo I entra aqui: o
servico le `PokemonInstancia` do banco, monta `StatsBase` com os seis campos
`*_base` da especie, e repassa ao dominio puro de `game/stats.py` e
`game/experience.py`. Nenhum calculo de stat ou de nivel mora neste arquivo.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.erros import RecursoNaoEncontrado
from app.game import balance
from app.game.experience import experiencia_para_o_proximo_nivel
from app.game.stats import StatsBase, calcular_stats_efetivos, hp_atual_absoluto
from app.models import PokemonInstancia
from app.repositories import pokemon as pokemon_repo
from app.repositories.pokemon import FiltrosPokemon
from app.schemas.pokemon import PaginaPokemon, PokemonDetalhe, PokemonResumo, StatsEfetivosLer


def listar(
    sessao: Session,
    laboratorio_id: uuid.UUID,
    filtros: FiltrosPokemon,
    *,
    page: int,
    page_size: int,
) -> PaginaPokemon:
    itens, total, page_efetivo, page_size_efetivo = pokemon_repo.listar(
        sessao, laboratorio_id, filtros, page=page, page_size=page_size
    )
    return PaginaPokemon(
        items=[PokemonResumo.de_modelo(pokemon) for pokemon in itens],
        total=total,
        page=page_efetivo,
        page_size=page_size_efetivo,
    )


def obter_detalhe(
    sessao: Session, laboratorio_id: uuid.UUID, pokemon_id: uuid.UUID
) -> PokemonDetalhe:
    pokemon = pokemon_repo.buscar_detalhe(sessao, laboratorio_id, pokemon_id)
    if pokemon is None:
        raise RecursoNaoEncontrado()
    return _montar_detalhe(pokemon)


def atualizar_apelido(
    sessao: Session, laboratorio_id: uuid.UUID, pokemon_id: uuid.UUID, apelido: str | None
) -> PokemonDetalhe:
    """Regra 5: apelido entre 1 e 50 caracteres (ja validado no schema); nulo limpa."""
    pokemon = pokemon_repo.buscar_detalhe(sessao, laboratorio_id, pokemon_id)
    if pokemon is None:
        raise RecursoNaoEncontrado()

    pokemon_repo.atualizar_apelido(pokemon, apelido)
    sessao.commit()

    return _montar_detalhe(pokemon)


def _montar_detalhe(pokemon: PokemonInstancia) -> PokemonDetalhe:
    especie = pokemon.especie
    stats_base = StatsBase(
        hp=especie.hp_base,
        ataque=especie.ataque_base,
        defesa=especie.defesa_base,
        ataque_especial=especie.ataque_especial_base,
        defesa_especial=especie.defesa_especial_base,
        velocidade=especie.velocidade_base,
    )
    stats = calcular_stats_efetivos(stats_base, pokemon.nivel)
    hp_atual = hp_atual_absoluto(stats.hp, pokemon.hp_atual_pct)

    # Criterio 6: no nivel maximo nao ha numero de EXP que faca sentido
    # mostrar. `nivel_maximo` e o campo que deixa isso explicito; o valor de
    # EXP some (vira nulo) em vez de virar um zero enganoso.
    nivel_maximo = pokemon.nivel >= balance.NIVEL_MAXIMO
    experiencia_restante = (
        None
        if nivel_maximo
        else experiencia_para_o_proximo_nivel(especie.curva_crescimento, pokemon.experiencia)
    )

    return PokemonDetalhe(
        id=pokemon.id,
        nome=pokemon.apelido or especie.nome,
        apelido=pokemon.apelido,
        especie_id=especie.id,
        especie_nome=especie.nome,
        tipo_primario=especie.tipo_primario,
        tipo_secundario=especie.tipo_secundario,
        sprite=especie.sprite_frente,
        nivel=pokemon.nivel,
        atribuido=pokemon.treinador_id is not None,
        treinador_id=pokemon.treinador_id,
        stats=StatsEfetivosLer.de_dominio(stats),
        hp_atual=hp_atual,
        hp_maximo=stats.hp,
        experiencia=pokemon.experiencia,
        experiencia_para_proximo_nivel=experiencia_restante,
        nivel_maximo=nivel_maximo,
        origem=pokemon.origem,
        local_captura=pokemon.local_captura.nome if pokemon.local_captura else None,
        capturado_em=pokemon.capturado_em,
        treinador_nome=pokemon.treinador.nome if pokemon.treinador else None,
    )
