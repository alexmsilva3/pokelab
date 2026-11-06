"""Caso de uso do corpo de treinadores (spec 004).

A fronteira do Artigo I entra aqui: o servico le `Treinador` e
`PokemonInstancia` do banco, monta as dataclasses enxutas que `game/team.py`,
`game/power.py` e `game/trainers.py` esperam, e repassa. Nenhuma regra de time
nem calculo de poder mora neste arquivo.

`definir_time` e `prever_time` chamam literalmente a mesma funcao de dominio
(`game.team.validar_time`, direto ou atraves de `game.team.prever_time`), para
que a previa nunca aceite o que o salvamento recusa (plan.md, secao 6).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core.erros import ConflitoDeTime, RecursoNaoEncontrado
from app.game import balance, team
from app.game import trainers as trainers_dominio
from app.game.power import PokemonNoTime, poder_do_time
from app.game.stats import StatsBase
from app.models import PokemonInstancia, Treinador
from app.repositories import treinadores as treinadores_repo
from app.schemas.pokemon import PokemonResumo
from app.schemas.trainers import (
    AvatarLer,
    ListaTrainers,
    PreviaTimeLer,
    TrainerDetalhe,
    TrainerResumo,
)


def _pokemon_no_time(pokemon: PokemonInstancia) -> PokemonNoTime:
    """`pokemon` precisa chegar com `especie` ja carregada (sem lazy load)."""
    especie = pokemon.especie
    base = StatsBase(
        hp=especie.hp_base,
        ataque=especie.ataque_base,
        defesa=especie.defesa_base,
        ataque_especial=especie.ataque_especial_base,
        defesa_especial=especie.defesa_especial_base,
        velocidade=especie.velocidade_base,
    )
    return PokemonNoTime.a_partir_dos_stats(base, pokemon.nivel, pokemon.hp_atual_pct)


def _poder_do_treinador(treinador: Treinador) -> int:
    return poder_do_time((_pokemon_no_time(pokemon) for pokemon in treinador.time), treinador.nivel)


def _campos_comuns(treinador: Treinador) -> dict:
    return {
        "id": treinador.id,
        "nome": treinador.nome,
        "avatar": AvatarLer(**treinador.avatar),
        "nivel": treinador.nivel,
        "experiencia": treinador.experiencia,
        "status": treinador.status,
        "ocupado": trainers_dominio.status_de(treinador.status).ocupado,
        "tamanho_maximo_time": balance.TAMANHO_MAXIMO_TIME,
        "time": [PokemonResumo.de_modelo(pokemon) for pokemon in treinador.time],
        "capacidade_bagagem": team.capacidade_bagagem_tolerante(len(treinador.time)),
    }


def _montar_resumo(treinador: Treinador) -> TrainerResumo:
    return TrainerResumo(**_campos_comuns(treinador))


def _montar_detalhe(treinador: Treinador) -> TrainerDetalhe:
    return TrainerDetalhe(
        **_campos_comuns(treinador),
        experiencia_para_proximo_nivel=trainers_dominio.experiencia_para_o_proximo_nivel(
            treinador.experiencia
        ),
        poder=_poder_do_treinador(treinador),
    )


def listar(sessao: Session, laboratorio_id: uuid.UUID) -> ListaTrainers:
    treinadores = treinadores_repo.listar(sessao, laboratorio_id)
    return ListaTrainers(items=[_montar_resumo(treinador) for treinador in treinadores])


def obter_detalhe(
    sessao: Session, laboratorio_id: uuid.UUID, treinador_id: uuid.UUID
) -> TrainerDetalhe:
    treinador = treinadores_repo.buscar_detalhe(sessao, laboratorio_id, treinador_id)
    if treinador is None:
        raise RecursoNaoEncontrado()
    return _montar_detalhe(treinador)


def _pokemon_conhecidos(pokemon: Sequence[PokemonInstancia]) -> list[team.PokemonParaTime]:
    """Traduz as linhas lidas do banco para o vocabulario do dominio.

    `comprometido_com_entrega` e sempre falso: a coluna `comprometido_entrega_id`
    so existe a partir da Fase 8, e ate la nenhum Pokemon pode estar
    reservado para uma entrega. Quando a coluna existir, esta linha vira
    `pokemon.comprometido_entrega_id is not None` e nada mais muda aqui nem em
    `game/team.py`.
    """
    return [
        team.PokemonParaTime(
            id=item.id, treinador_id=item.treinador_id, comprometido_com_entrega=False
        )
        for item in pokemon
    ]


def _alvo(treinador: Treinador) -> team.TreinadorAlvo:
    return team.TreinadorAlvo(id=treinador.id, status=trainers_dominio.status_de(treinador.status))


def definir_time(
    sessao: Session,
    laboratorio_id: uuid.UUID,
    treinador_id: uuid.UUID,
    pokemon_ids: Sequence[uuid.UUID],
) -> TrainerDetalhe:
    """Substituicao total do time, sob lock (Artigo VII, plan.md secao 5).

    Trava a linha do treinador e as dos Pokemon envolvidos na mesma transacao
    antes de validar: e o que impede dois `PUT` concorrentes em treinadores
    diferentes de atribuirem o mesmo Pokemon aos dois.
    """
    # As checagens que nao dependem do banco vem antes do lock: uma lista com
    # mil ids travaria mil linhas so para ser recusada por tamanho logo depois.
    try:
        team.validar_pedido(pokemon_ids)
    except team.ErroDeTime as erro:
        raise ConflitoDeTime(erro) from erro

    treinador = treinadores_repo.travar_treinador(sessao, laboratorio_id, treinador_id)
    if treinador is None:
        raise RecursoNaoEncontrado()

    pokemon_envolvidos = treinadores_repo.travar_pokemon_envolvidos(
        sessao, laboratorio_id, treinador_id, pokemon_ids
    )
    pokemon_por_id = {item.id: item for item in pokemon_envolvidos}

    try:
        time_validado = team.validar_time(
            _alvo(treinador), pokemon_ids, _pokemon_conhecidos(pokemon_envolvidos)
        )
    except team.ErroDeTime as erro:
        sessao.rollback()
        raise ConflitoDeTime(erro) from erro

    treinadores_repo.aplicar_time(
        pokemon_por_id,
        treinador_id=treinador.id,
        para_adicionar=time_validado.para_adicionar,
        para_remover=time_validado.para_remover,
    )
    sessao.commit()

    atualizado = treinadores_repo.buscar_detalhe(sessao, laboratorio_id, treinador_id)
    if atualizado is None:  # pragma: no cover - impossivel, acabamos de gravar nele
        raise RecursoNaoEncontrado()
    return _montar_detalhe(atualizado)


def prever_time(
    sessao: Session,
    laboratorio_id: uuid.UUID,
    treinador_id: uuid.UUID,
    pokemon_ids: Sequence[uuid.UUID],
) -> PreviaTimeLer:
    """Valida sem gravar, com a mesma funcao de dominio que `definir_time` usa.

    Sem lock de proposito: a previa nao escreve nada, entao nao ha o que
    proteger de concorrencia aqui. O `PUT` revalida tudo sob lock antes de
    gravar, e e essa segunda validacao que vale.
    """
    treinador = treinadores_repo.buscar_detalhe(sessao, laboratorio_id, treinador_id)
    if treinador is None:
        raise RecursoNaoEncontrado()

    pokemon_relevantes = treinadores_repo.buscar_pokemon_envolvidos(
        sessao, laboratorio_id, treinador_id, pokemon_ids
    )
    pokemon_por_id = {item.id: item for item in pokemon_relevantes}

    previa = team.prever_time(
        _alvo(treinador), pokemon_ids, _pokemon_conhecidos(pokemon_relevantes)
    )

    if previa.valido and previa.time is not None:
        membros = [pokemon_por_id[pokemon_id] for pokemon_id in previa.time.pokemon_ids]
        poder = poder_do_time((_pokemon_no_time(item) for item in membros), treinador.nivel)
        capacidade = previa.time.capacidade_bagagem
    else:
        # Regra do dominio (team.py): composicao recusada nao muda nada, entao
        # o que a tela deve continuar mostrando e o time ATUAL, nao o
        # hipotetico.
        poder = _poder_do_treinador(treinador)
        capacidade = team.capacidade_bagagem(len(treinador.time))

    return PreviaTimeLer(
        valido=previa.valido,
        poder=poder,
        capacidade_bagagem=capacidade,
        codigo=previa.codigo,
        motivo=previa.motivo,
    )
