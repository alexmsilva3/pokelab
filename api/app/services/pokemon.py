"""Caso de uso do acervo de Pokemon do laboratorio (spec 003).

Fase so de leitura, exceto o apelido. A fronteira do Artigo I entra aqui: o
servico le `PokemonInstancia` do banco, monta `StatsBase` com os seis campos
`*_base` da especie, e repassa ao dominio puro de `game/stats.py` e
`game/experience.py`. Nenhum calculo de stat ou de nivel mora neste arquivo.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.erros import ConflitoDeSoltura, RecursoNaoEncontrado
from app.game import balance
from app.game import soltar as soltar_dominio
from app.game import trainers as trainers_dominio
from app.game.experience import experiencia_para_o_proximo_nivel
from app.game.stats import StatsBase, calcular_stats_efetivos, hp_atual_absoluto
from app.models import PokemonInstancia
from app.repositories import laboratorios as laboratorios_repo
from app.repositories import pokemon as pokemon_repo
from app.repositories import treinadores as treinadores_repo
from app.repositories.pokemon import FiltrosPokemon
from app.schemas.pokemon import PaginaPokemon, PokemonDetalhe, PokemonResumo, StatsEfetivosLer
from app.services import relogio


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
    agora = datetime.now(UTC)
    escala = get_settings().expedition_time_scale
    return PaginaPokemon(
        items=[
            PokemonResumo.de_modelo(pokemon, hp_atual_pct=_hp_observado(pokemon, agora, escala))
            for pokemon in itens
        ],
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


# --- Soltar (spec 008, invariantes 24 e 25) ----------------------------------


def soltar(sessao: Session, laboratorio_id: uuid.UUID, pokemon_id: uuid.UUID) -> None:
    """`DELETE /pokemon/{id}`: devolve a natureza, sem recompensa (SDD 4.10).

    Sem valor de retorno, como o proprio `game.soltar` (plan.md, criterio 7:
    nada muda alem do Pokemon sumir e a ocupacao cair). Remove a linha de
    verdade — sem soft delete, porque nao ha para que voltar.

    **Ordem de lock (Artigo VII) — esta e a ordem CANONICA do projeto
    inteiro, referenciada por `trainers_service.definir_time` e por
    `entregas_service.aceitar`/`claim`/`refresh`:** Pokemon primeiro (e a
    linha que o pedido identifica), o treinador dele depois se houver um
    (para ler o status sob trava, nao um instantaneo que um despacho
    concorrente pode ter mudado por baixo), e o laboratorio por ultimo, so
    para a CONTAGEM — sem travar o laboratorio, duas solturas do ultimo par
    de Pokemon de um laboratorio de dois poderiam ler `total=2` as duas e as
    duas passarem, esvaziando o acervo (invariante 25). A mesma trava protege
    a conclusao de expedicao (que insere capturas) e a conclusao de entrega
    (que remove Pokemon), entao a soltura entra na mesma fila.

    Pokemon-antes-do-treinador nao e escolha arbitraria: esta funcao so
    descobre QUAL treinador travar depois de ler o Pokemon (o pedido so traz
    `pokemon_id`), entao travar o treinador primeiro exigiria adivinhar quem
    e antes de ler a linha que diz quem e. As DUAS outras operacoes que
    travam Pokemon e treinador juntos — `definir_time` e `aceitar` — recebem
    os dois ids prontos no pedido, e foram alinhadas a esta ordem (nao o
    contrario) exatamente por isso: inverter aqui era impossivel sem uma
    segunda consulta e um laco de nova tentativa; alinhar as outras duas era
    so trocar a ordem de duas chamadas. Laboratorio, quando qualquer destas
    operacoes precisa dele, e sempre o ULTIMO lock da transacao — e por isso
    `entregas_service.refresh` trava as entregas que vai descartar ANTES do
    laboratorio, nunca depois (revisao da Fase 8, achado "dois deadlocks").
    """
    pokemon = pokemon_repo.travar_para_soltar(sessao, laboratorio_id, pokemon_id)
    if pokemon is None:
        raise RecursoNaoEncontrado()

    treinador_do_pokemon: soltar_dominio.TreinadorDoPokemon | None = None
    if pokemon.treinador_id is not None:
        treinador = treinadores_repo.travar_treinador(sessao, laboratorio_id, pokemon.treinador_id)
        if treinador is None:  # pragma: no cover - FK garante a existencia
            sessao.rollback()
            raise RecursoNaoEncontrado()
        treinador_do_pokemon = soltar_dominio.TreinadorDoPokemon(
            id=treinador.id,
            nome=treinador.nome,
            status=trainers_dominio.status_de(treinador.status),
        )

    laboratorio = laboratorios_repo.travar(sessao, laboratorio_id)
    if laboratorio is None:  # pragma: no cover - FK garante a existencia
        sessao.rollback()
        raise RecursoNaoEncontrado()
    total_do_laboratorio = pokemon_repo.contar(sessao, laboratorio_id)

    pokemon_do_laboratorio = soltar_dominio.PokemonDoLaboratorio(
        id=pokemon.id,
        treinador_id=pokemon.treinador_id,
        comprometido_entrega_id=pokemon.comprometido_entrega_id,
    )

    try:
        soltar_dominio.pode_soltar(
            pokemon_do_laboratorio, treinador_do_pokemon, total_do_laboratorio
        )
    except soltar_dominio.ErroDeSoltura as erro:
        sessao.rollback()
        raise ConflitoDeSoltura(erro) from erro

    pokemon_repo.excluir(sessao, pokemon)
    sessao.commit()


def _hp_observado(pokemon: PokemonInstancia, agora: datetime, escala: float) -> int:
    """O `hp_atual_pct` que a leitura mostra: o gravado mais a recuperacao passiva.

    Fronteira do Artigo I (spec 007, criterios 20 e 21): o relogio e a escala
    de tempo (`EXPEDITION_TIME_SCALE`) sao lidos aqui, nunca em `app.game`.

    Invariante 18: a enfermaria so corre no laboratorio. Um Pokemon cujo
    treinador esta `EM_EXPEDICAO` (ou `EM_ENTREGA`, quando essa feature
    existir) nao recupera nada, mesmo que muito tempo real tenha passado
    desde `hp_atualizado_em` — ele esta em campo, nao parado na enfermaria.
    `pokemon.treinador` precisa chegar carregado (sem lazy load).
    """
    if (
        pokemon.treinador is not None
        and trainers_dominio.status_de(pokemon.treinador.status).ocupado
    ):
        return pokemon.hp_atual_pct
    return relogio.hp_observado(
        pokemon.hp_atual_pct, pokemon.hp_atualizado_em, agora=agora, escala=escala
    )


def _montar_detalhe(pokemon: PokemonInstancia) -> PokemonDetalhe:
    agora = datetime.now(UTC)
    escala = get_settings().expedition_time_scale
    hp_pct = _hp_observado(pokemon, agora, escala)

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
    hp_atual = hp_atual_absoluto(stats.hp, hp_pct)

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
        hp_atual_pct=hp_pct,
        hp_atualizado_em=pokemon.hp_atualizado_em,
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
