"""Poder do Pokemon e do time (SDD 4.3).

    poder_pokemon = nivel * (1 + soma_stats_base / 600) * (hp_atual_pct / 100)
    poder_time    = soma(poder_pokemon) * (1 + nivel_treinador * 0.03)

Os valores da tabela abaixo foram calculados a mao a partir dessa formula, e
nao copiados da saida do codigo: uma tabela extraida da implementacao so prova
que a implementacao faz o que faz.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.game import balance
from app.game.erros import HpAtualInvalido, NivelInvalido, StatInvalido
from app.game.power import PokemonNoTime, poder_do_time, poder_pokemon, somar_stats_base
from app.game.stats import StatsBase
from app.game.trainers import NivelDeTreinadorInvalido

# Bulbasaur: 45 + 49 + 49 + 65 + 65 + 45 = 318.
BULBASAUR = StatsBase(
    hp=45, ataque=49, defesa=49, ataque_especial=65, defesa_especial=65, velocidade=45
)


def um(nivel: int = 5, soma: int = 300, hp: int = 100) -> PokemonNoTime:
    return PokemonNoTime(nivel=nivel, soma_stats_base=soma, hp_atual_pct=hp)


@pytest.mark.parametrize(
    ("nivel", "soma", "hp", "esperado"),
    [
        # nivel * (1 + soma/600) * hp/100, arredondado uma unica vez no fim,
        # para CASAS_DECIMAIS_PODER casas.
        (1, 0, 100, 1.0),  # 1 * 1.000 * 1.0  = 1
        (5, 600, 100, 10.0),  # 5 * 2.000 * 1.0  = 10
        (5, 318, 100, 7.6),  # 5 * 1.530 * 1.0  = 7.65
        (7, 195, 100, 9.3),  # 7 * 1.325 * 1.0  = 9.275
        (10, 300, 40, 6.0),  # 10 * 1.500 * 0.4 = 6
        (10, 300, 50, 7.5),  # 10 * 1.500 * 0.5 = 7.5
        (20, 525, 80, 30.0),  # 20 * 1.875 * 0.8 = 30
        (50, 600, 50, 50.0),  # 50 * 2.000 * 0.5 = 50
        (100, 600, 100, 200.0),  # 100 * 2.000 * 1.0 = 200
        (30, 300, 0, 0.0),  # nocauteado nao contribui
    ],
)
def test_tabela_de_poder_individual(nivel, soma, hp, esperado):
    assert poder_pokemon(um(nivel, soma, hp)) == esperado


@pytest.mark.parametrize(
    ("nivel_treinador", "esperado"),
    [
        # Tres Bulbasaur de nivel 5: 7.65 cada, 22.95 no time.
        (1, 23.6),  # 22.95 * 1.03 = 23.6385
        (5, 26.4),  # 22.95 * 1.15 = 26.3925
        (10, 29.8),  # 22.95 * 1.30 = 29.835
        (20, 36.7),  # 22.95 * 1.60 = 36.72
    ],
)
def test_tabela_de_poder_do_time(nivel_treinador, esperado):
    time = [um(5, 318, 100) for _ in range(balance.TAMANHO_MAXIMO_TIME)]
    assert poder_do_time(time, nivel_treinador) == esperado


def test_time_vazio_vale_zero_e_nao_e_erro():
    # Regra 10 da spec 004: treinador sem Pokemon e estado valido, e a previa
    # precisa saber dizer isso antes de o professor escolher alguem.
    assert poder_do_time([], nivel_treinador=1) == 0
    assert poder_do_time([], nivel_treinador=50) == 0


def test_poder_cresce_com_o_nivel_do_pokemon():
    poderes = [poder_pokemon(um(nivel=nivel)) for nivel in range(1, 101)]
    assert poderes == sorted(poderes)
    assert poderes[0] < poderes[-1]


def test_poder_cresce_com_os_stats_da_especie():
    fraco = poder_pokemon(um(soma=200))
    medio = poder_pokemon(um(soma=400))
    forte = poder_pokemon(um(soma=600))
    assert fraco < medio < forte


def test_poder_cresce_com_o_nivel_do_treinador():
    # Criterio de aceite 9: mesmos Pokemon, treinador de nivel maior, poder maior.
    time = [um(20, 500, 100), um(18, 420, 100)]
    poderes = [poder_do_time(time, nivel) for nivel in range(1, 31)]
    assert poderes == sorted(poderes)
    assert poderes[0] < poderes[-1]


def test_pokemon_machucado_vale_menos_que_o_mesmo_pokemon_inteiro():
    inteiro = poder_pokemon(um(nivel=40, soma=500, hp=100))
    machucado = poder_pokemon(um(nivel=40, soma=500, hp=30))
    nocauteado = poder_pokemon(um(nivel=40, soma=500, hp=0))
    assert nocauteado == 0
    assert nocauteado < machucado < inteiro


def test_time_machucado_vale_menos_que_o_mesmo_time_inteiro():
    inteiro = [um(30, 450, 100), um(25, 400, 100)]
    machucado = [um(30, 450, 45), um(25, 400, 45)]
    assert poder_do_time(machucado, 3) < poder_do_time(inteiro, 3)


def test_pokemon_a_mais_no_time_nunca_reduz_o_poder():
    dupla = [um(10, 300, 100), um(12, 320, 100)]
    trio = [*dupla, um(1, 10, 1)]
    assert poder_do_time(trio, 1) >= poder_do_time(dupla, 1)


def test_ordem_do_time_nao_muda_o_poder():
    time = [um(10, 318, 100), um(25, 500, 60), um(7, 195, 90)]
    assert poder_do_time(time, 4) == poder_do_time(list(reversed(time)), 4)


def test_poder_sai_com_a_precisao_do_balance():
    # Inteiro escondia o bonus do treinador em times pequenos: um Bulbasaur
    # nivel 5 dava 8 com treinador de nivel 1, 2 ou 3, e o criterio de aceite 9
    # da spec 004 era falso na pratica.
    casas = balance.CASAS_DECIMAIS_PODER
    for valor in (poder_pokemon(um(7, 195, 73)), poder_do_time([um(7, 195, 73)], 3)):
        assert isinstance(valor, float)
        assert round(valor, casas) == valor


def test_cada_nivel_de_treinador_muda_o_poder_do_time():
    # Criterio de aceite 9 da spec 004, no caso mais apertado: um unico Pokemon
    # de nivel baixo, onde o passo de 3% e menor.
    time = [um(5, 318, 100)]
    poderes = [poder_do_time(time, nivel) for nivel in range(1, 11)]
    assert len(set(poderes)) == len(poderes), poderes
    assert poderes == sorted(poderes)


def test_poder_e_deterministico():
    # Artigo III: mesma entrada, mesma saida, sempre. Sem ponto flutuante
    # acumulando erro, repetir a conta nao muda o resultado.
    time = [um(13, 318, 77), um(44, 525, 31), um(2, 195, 5)]
    primeira = [poder_do_time(time, nivel) for nivel in range(1, 20)]
    segunda = [poder_do_time(time, nivel) for nivel in range(1, 20)]
    assert primeira == segunda


def test_soma_de_stats_base_usa_os_seis_stats():
    assert somar_stats_base(BULBASAUR) == 318


def test_pokemon_pode_ser_montado_a_partir_dos_stats_base():
    direto = um(5, 318, 80)
    pelos_stats = PokemonNoTime.a_partir_dos_stats(BULBASAUR, nivel=5, hp_atual_pct=80)
    assert pelos_stats == direto
    assert poder_pokemon(pelos_stats) == poder_pokemon(direto)


def test_entrada_e_imutavel():
    pokemon = um()
    with pytest.raises(FrozenInstanceError):
        pokemon.nivel = 99  # type: ignore[misc]


@pytest.mark.parametrize("nivel", [0, -1, balance.NIVEL_MAXIMO + 1])
def test_nivel_fora_da_faixa_e_recusado(nivel):
    with pytest.raises(NivelInvalido):
        poder_pokemon(um(nivel=nivel))


@pytest.mark.parametrize("hp", [-1, 101])
def test_hp_fora_da_faixa_e_recusado(hp):
    with pytest.raises(HpAtualInvalido):
        poder_pokemon(um(hp=hp))


def test_soma_de_stats_negativa_e_recusada():
    with pytest.raises(StatInvalido):
        poder_pokemon(um(soma=-1))


@pytest.mark.parametrize("nivel", [0, -3, balance.NIVEL_MAXIMO + 1])
def test_nivel_de_treinador_fora_da_faixa_e_recusado(nivel):
    with pytest.raises(NivelDeTreinadorInvalido):
        poder_do_time([um()], nivel_treinador=nivel)


def test_membro_invalido_e_recusado_mesmo_dentro_de_um_time_valido():
    with pytest.raises(NivelInvalido):
        poder_do_time([um(), um(nivel=0)], nivel_treinador=1)
