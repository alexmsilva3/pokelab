"""Composicao do time (spec 004) e os invariantes do SDD 3.3 que a governam.

Cada invariante tem um teste que tenta viola-lo e confere que a recusa veio com
o erro especifico daquela violacao — um erro generico nao serviria para a
previa, que mostra o motivo ao professor enquanto ele monta o time.

Mapa entre a numeracao do SDD 3.3 e a da spec 004:

    SDD 1  / spec 2   maximo de Pokemon no time        TimeCheio
    SDD 2  / spec 3   um dono por Pokemon              PokemonJaAtribuido
    SDD 3  / spec 4   treinador ocupado nao muda time  TreinadorOcupado
    SDD 4  / spec 5   Pokemon de ocupado nao sai       TreinadorOcupado / PokemonJaAtribuido
    SDD 14 / spec 6   comprometido com entrega         PokemonComprometido
    SDD 11 / spec 7   capacidade de bagagem            capacidade_bagagem
           / spec 11  escopo do laboratorio            PokemonDesconhecido
           / crit. 11 Pokemon repetido na lista        PokemonDuplicado

Os invariantes 5 e 6 do SDD nao sao deste modulo: o limite de treinadores do
laboratorio esta em test_game_laboratorio.py e a vizinhanca do destino de
expedicao e da Fase 6.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from app.game import balance
from app.game.team import (
    PokemonComprometido,
    PokemonDesconhecido,
    PokemonDuplicado,
    PokemonJaAtribuido,
    PokemonParaTime,
    TamanhoDeTimeInvalido,
    TimeCheio,
    TreinadorAlvo,
    TreinadorOcupado,
    capacidade_bagagem,
    prever_time,
    time_atual,
    validar_time,
)
from app.game.trainers import StatusTreinador

ASH = UUID(int=1)
MISTY = UUID(int=2)

BULBA = UUID(int=10)
CHARMANDER = UUID(int=11)
SQUIRTLE = UUID(int=12)
PIDGEY = UUID(int=13)
FORASTEIRO = UUID(int=99)

LIVRES = (
    PokemonParaTime(id=BULBA),
    PokemonParaTime(id=CHARMANDER),
    PokemonParaTime(id=SQUIRTLE),
    PokemonParaTime(id=PIDGEY),
)


def treinador(
    status: StatusTreinador = StatusTreinador.DISPONIVEL, id: UUID = ASH
) -> TreinadorAlvo:
    return TreinadorAlvo(id=id, status=status)


# --- Capacidade de bagagem (SDD 11, spec 7 e 8) ------------------------------


@pytest.mark.parametrize(("tamanho", "esperado"), [(0, 6), (1, 5), (2, 4), (3, 3)])
def test_capacidade_de_bagagem_por_tamanho_de_time(tamanho, esperado):
    assert capacidade_bagagem(tamanho) == esperado


def test_capacidade_de_bagagem_sai_de_balance_e_nao_de_numero_fixo():
    assert capacidade_bagagem(0) == balance.CAPACIDADE_TOTAL_TREINADOR
    assert capacidade_bagagem(balance.TAMANHO_MAXIMO_TIME) == (
        balance.CAPACIDADE_TOTAL_TREINADOR - balance.TAMANHO_MAXIMO_TIME
    )


def test_capacidade_de_bagagem_nunca_e_negativa_nem_passa_do_total():
    for tamanho in range(balance.TAMANHO_MAXIMO_TIME + 1):
        assert 0 <= capacidade_bagagem(tamanho) <= balance.CAPACIDADE_TOTAL_TREINADOR


def test_capacidade_de_time_maior_que_o_maximo_e_recusada():
    with pytest.raises(TimeCheio):
        capacidade_bagagem(balance.TAMANHO_MAXIMO_TIME + 1)


def test_capacidade_de_tamanho_negativo_e_recusada():
    with pytest.raises(TamanhoDeTimeInvalido):
        capacidade_bagagem(-1)


def test_time_validado_carrega_a_propria_capacidade():
    time = validar_time(treinador(), [BULBA], LIVRES)
    assert time.tamanho == 1
    assert time.capacidade_bagagem == 5


# --- Caminho feliz -----------------------------------------------------------


def test_time_vazio_e_composicao_valida():
    # Regra 10 da spec: treinador sem Pokemon e como todos comecam.
    time = validar_time(treinador(), [], LIVRES)
    assert time.pokemon_ids == ()
    assert time.capacidade_bagagem == balance.CAPACIDADE_TOTAL_TREINADOR


def test_time_aceita_ate_o_maximo_de_pokemon_livres():
    time = validar_time(treinador(), [BULBA, CHARMANDER, SQUIRTLE], LIVRES)
    assert time.pokemon_ids == (BULBA, CHARMANDER, SQUIRTLE)
    assert time.para_adicionar == (BULBA, CHARMANDER, SQUIRTLE)
    assert time.para_remover == ()
    assert time.capacidade_bagagem == 3


def test_substituicao_total_devolve_quem_entra_e_quem_sai():
    # Spec 004, regra 9: definir o time substitui o time inteiro; o que nao foi
    # listado volta ao laboratorio.
    estado = (
        PokemonParaTime(id=BULBA, treinador_id=ASH),
        PokemonParaTime(id=CHARMANDER, treinador_id=ASH),
        PokemonParaTime(id=SQUIRTLE),
    )
    time = validar_time(treinador(), [BULBA, SQUIRTLE], estado)
    assert time.para_adicionar == (SQUIRTLE,)
    assert time.para_remover == (CHARMANDER,)


def test_manter_o_mesmo_time_nao_move_ninguem():
    estado = (PokemonParaTime(id=BULBA, treinador_id=ASH),)
    time = validar_time(treinador(), [BULBA], estado)
    assert time.para_adicionar == ()
    assert time.para_remover == ()


def test_esvaziar_o_time_devolve_todos_ao_laboratorio():
    estado = (
        PokemonParaTime(id=BULBA, treinador_id=ASH),
        PokemonParaTime(id=CHARMANDER, treinador_id=ASH),
    )
    time = validar_time(treinador(), [], estado)
    assert time.pokemon_ids == ()
    assert time.para_remover == (BULBA, CHARMANDER)


def test_time_atual_lista_so_os_pokemon_do_treinador():
    estado = (
        PokemonParaTime(id=BULBA, treinador_id=ASH),
        PokemonParaTime(id=CHARMANDER, treinador_id=MISTY),
        PokemonParaTime(id=SQUIRTLE),
    )
    assert time_atual(ASH, estado) == (BULBA,)
    assert time_atual(MISTY, estado) == (CHARMANDER,)


def test_resultado_validado_e_imutavel():
    time = validar_time(treinador(), [BULBA], LIVRES)
    with pytest.raises(FrozenInstanceError):
        time.pokemon_ids = ()  # type: ignore[misc]


def test_validacao_e_deterministica():
    # Artigo III: a mesma composicao, validada duas vezes, da o mesmo time.
    primeira = validar_time(treinador(), [SQUIRTLE, BULBA], LIVRES)
    segunda = validar_time(treinador(), [SQUIRTLE, BULBA], LIVRES)
    assert primeira == segunda


# --- Invariante 1 do SDD / regra 2 da spec: maximo de Pokemon no time --------


def test_time_acima_do_maximo_e_recusado_com_erro_de_time_cheio():
    with pytest.raises(TimeCheio) as recusa:
        validar_time(treinador(), [BULBA, CHARMANDER, SQUIRTLE, PIDGEY], LIVRES)
    assert recusa.value.codigo == "TIME_CHEIO"
    assert str(balance.TAMANHO_MAXIMO_TIME) in str(recusa.value)


# --- Invariante 2 do SDD / regra 3 da spec: um dono por Pokemon --------------


def test_pokemon_de_outro_treinador_e_recusado_com_erro_proprio():
    estado = (PokemonParaTime(id=BULBA, treinador_id=MISTY),)
    with pytest.raises(PokemonJaAtribuido) as recusa:
        validar_time(treinador(), [BULBA], estado)
    assert recusa.value.codigo == "POKEMON_JA_ATRIBUIDO"
    assert recusa.value.detalhes["pokemon_id"] == str(BULBA)


def test_pokemon_que_ja_e_do_proprio_treinador_continua_aceito():
    estado = (PokemonParaTime(id=BULBA, treinador_id=ASH),)
    assert validar_time(treinador(), [BULBA], estado).pokemon_ids == (BULBA,)


# --- Invariante 3 do SDD / regra 4 da spec: treinador ocupado ----------------


@pytest.mark.parametrize("status", [StatusTreinador.EM_EXPEDICAO, StatusTreinador.EM_ENTREGA])
def test_treinador_ocupado_nao_tem_o_time_alterado(status):
    with pytest.raises(TreinadorOcupado) as recusa:
        validar_time(treinador(status), [BULBA], LIVRES)
    assert recusa.value.codigo == "TREINADOR_OCUPADO"
    assert recusa.value.detalhes["status"] == status.value


def test_treinador_ocupado_e_recusado_antes_de_qualquer_outro_motivo():
    # O motivo que o professor precisa ler e o bloqueio, nao o tamanho da lista.
    with pytest.raises(TreinadorOcupado):
        validar_time(
            treinador(StatusTreinador.EM_EXPEDICAO),
            [BULBA, BULBA, CHARMANDER, SQUIRTLE, PIDGEY],
            LIVRES,
        )


def test_treinador_descansando_ainda_pode_remontar_o_time():
    # DESCANSANDO nao e ocupado: ele voltou, esta no laboratorio, e o descanso
    # adia a proxima missao, nao a arrumacao do time.
    time = validar_time(treinador(StatusTreinador.DESCANSANDO), [BULBA], LIVRES)
    assert time.pokemon_ids == (BULBA,)


# --- Invariante 4 do SDD / regra 5 da spec: Pokemon de ocupado nao sai -------


def test_pokemon_de_treinador_ocupado_nao_sai_pelo_proprio_treinador():
    estado = (PokemonParaTime(id=BULBA, treinador_id=ASH),)
    with pytest.raises(TreinadorOcupado):
        validar_time(treinador(StatusTreinador.EM_EXPEDICAO), [], estado)


def test_pokemon_de_treinador_ocupado_nao_sai_por_outro_treinador():
    estado = (PokemonParaTime(id=BULBA, treinador_id=MISTY),)
    with pytest.raises(PokemonJaAtribuido):
        validar_time(treinador(id=ASH), [BULBA], estado)


# --- Invariante 14 do SDD / regra 6 da spec: comprometido com entrega --------


def test_pokemon_comprometido_com_entrega_nao_entra_em_time():
    estado = (PokemonParaTime(id=BULBA, comprometido_com_entrega=True),)
    with pytest.raises(PokemonComprometido) as recusa:
        validar_time(treinador(), [BULBA], estado)
    assert recusa.value.codigo == "POKEMON_COMPROMETIDO"
    assert recusa.value.detalhes["pokemon_id"] == str(BULBA)


def test_entrega_tem_precedencia_sobre_atribuicao_na_mensagem():
    # Um Pokemon reservado para entrega e de outro treinador tem dois
    # impedimentos; o que o professor precisa resolver primeiro e a entrega.
    estado = (PokemonParaTime(id=BULBA, treinador_id=MISTY, comprometido_com_entrega=True),)
    with pytest.raises(PokemonComprometido):
        validar_time(treinador(), [BULBA], estado)


# --- Criterio 11 da spec: Pokemon repetido na lista -------------------------


def test_pokemon_repetido_na_lista_e_recusado_com_erro_proprio():
    with pytest.raises(PokemonDuplicado) as recusa:
        validar_time(treinador(), [BULBA, BULBA], LIVRES)
    assert recusa.value.codigo == "POKEMON_DUPLICADO"
    assert recusa.value.detalhes["pokemon_id"] == str(BULBA)


def test_lista_repetida_nao_vira_time_cheio():
    # Tres ids com um repetido somam dois Pokemon distintos: recusar por
    # tamanho mandaria o professor remover alguem sem necessidade.
    with pytest.raises(PokemonDuplicado):
        validar_time(treinador(), [BULBA, CHARMANDER, BULBA], LIVRES)


# --- Regra 11 da spec: escopo do laboratorio --------------------------------


def test_pokemon_fora_do_laboratorio_e_recusado():
    with pytest.raises(PokemonDesconhecido) as recusa:
        validar_time(treinador(), [FORASTEIRO], LIVRES)
    assert recusa.value.codigo == "POKEMON_DESCONHECIDO"
    assert recusa.value.detalhes["pokemon_id"] == str(FORASTEIRO)


# --- Previa e salvamento usam a mesma validacao -----------------------------

COMPOSICOES_VALIDAS = [
    (),
    (BULBA,),
    (BULBA, CHARMANDER),
    (BULBA, CHARMANDER, SQUIRTLE),
    (SQUIRTLE, BULBA),
]

COMPOSICOES_INVALIDAS = [
    ([BULBA, CHARMANDER, SQUIRTLE, PIDGEY], LIVRES, TimeCheio),
    ([BULBA, BULBA], LIVRES, PokemonDuplicado),
    ([FORASTEIRO], LIVRES, PokemonDesconhecido),
    ([BULBA], (PokemonParaTime(id=BULBA, treinador_id=MISTY),), PokemonJaAtribuido),
    (
        [BULBA],
        (PokemonParaTime(id=BULBA, comprometido_com_entrega=True),),
        PokemonComprometido,
    ),
]


@pytest.mark.parametrize("pedido", COMPOSICOES_VALIDAS)
def test_previa_aceita_o_que_o_salvamento_aceita(pedido):
    salvo = validar_time(treinador(), list(pedido), LIVRES)
    previa = prever_time(treinador(), list(pedido), LIVRES)
    assert previa.valido is True
    assert previa.motivo is None
    assert previa.time == salvo


@pytest.mark.parametrize(("pedido", "estado", "erro"), COMPOSICOES_INVALIDAS)
def test_previa_recusa_o_que_o_salvamento_recusa_com_o_mesmo_motivo(pedido, estado, erro):
    with pytest.raises(erro) as recusa:
        validar_time(treinador(), pedido, estado)
    previa = prever_time(treinador(), pedido, estado)
    assert previa.valido is False
    assert previa.time is None
    assert previa.codigo == recusa.value.codigo
    assert previa.motivo == str(recusa.value)


def test_previa_de_treinador_ocupado_explica_em_vez_de_so_recusar():
    previa = prever_time(treinador(StatusTreinador.EM_ENTREGA), [BULBA], LIVRES)
    assert previa.valido is False
    assert previa.codigo == "TREINADOR_OCUPADO"
    assert "em entrega" in previa.motivo
