"""Stats efetivos (SDD 4.2).

Tabela de valores conhecidos calculados a mao, as propriedades que a formula
tem de manter em qualquer nivel e os limites do HP absoluto.
"""

from itertools import pairwise

import pytest

from app.game import balance
from app.game.erros import HpAtualInvalido, NivelInvalido, StatInvalido
from app.game.stats import StatsBase, StatsEfetivos, calcular_stats_efetivos, hp_atual_absoluto

BULBASAUR = StatsBase(
    hp=45,
    ataque=49,
    defesa=49,
    ataque_especial=65,
    defesa_especial=65,
    velocidade=45,
)

# Conta a mao, nivel a nivel:
#   hp   = floor(45 * 2 * n / 100) + n + 10
#   atk  = floor(49 * 2 * n / 100) + 5
#   spa  = floor(65 * 2 * n / 100) + 5
#   spe  = floor(45 * 2 * n / 100) + 5
TABELA_BULBASAUR = [
    # nivel 1: 0 + 1 + 10; 0 + 5; 1 + 5; 0 + 5
    (
        1,
        StatsEfetivos(
            hp=11, ataque=5, defesa=5, ataque_especial=6, defesa_especial=6, velocidade=5
        ),
    ),
    # nivel 5: 4 + 5 + 10; 4 + 5; 6 + 5; 4 + 5
    (
        5,
        StatsEfetivos(
            hp=19, ataque=9, defesa=9, ataque_especial=11, defesa_especial=11, velocidade=9
        ),
    ),
    # nivel 50: 45 + 50 + 10; 49 + 5; 65 + 5; 45 + 5
    (
        50,
        StatsEfetivos(
            hp=105, ataque=54, defesa=54, ataque_especial=70, defesa_especial=70, velocidade=50
        ),
    ),
    # nivel 100: 90 + 100 + 10; 98 + 5; 130 + 5; 90 + 5
    (
        100,
        StatsEfetivos(
            hp=200, ataque=103, defesa=103, ataque_especial=135, defesa_especial=135, velocidade=95
        ),
    ),
]


@pytest.mark.parametrize(("nivel", "esperado"), TABELA_BULBASAUR)
def test_stats_de_bulbasaur_nos_niveis_conhecidos(nivel, esperado):
    assert calcular_stats_efetivos(BULBASAUR, nivel) == esperado


def test_stats_sao_imutaveis():
    stats = calcular_stats_efetivos(BULBASAUR, balance.STARTER_LEVEL)
    with pytest.raises(AttributeError):
        stats.hp = 999


def test_mesma_entrada_devolve_o_mesmo_resultado():
    # Artigo III: a formula nao tem estado nem relogio escondido.
    primeira = calcular_stats_efetivos(BULBASAUR, 37)
    segunda = calcular_stats_efetivos(BULBASAUR, 37)
    assert primeira == segunda


def test_cada_stat_cresce_monotonicamente_com_o_nivel():
    por_nivel = [
        calcular_stats_efetivos(BULBASAUR, nivel) for nivel in range(1, balance.NIVEL_MAXIMO + 1)
    ]
    for menor, maior in pairwise(por_nivel):
        assert maior.hp >= menor.hp
        assert maior.ataque >= menor.ataque
        assert maior.defesa >= menor.defesa
        assert maior.ataque_especial >= menor.ataque_especial
        assert maior.defesa_especial >= menor.defesa_especial
        assert maior.velocidade >= menor.velocidade


def test_hp_e_sempre_maior_que_os_demais_stats_da_mesma_base():
    # O bonus do HP e + nivel + 10 contra + 5: a diferenca nunca se fecha.
    base = StatsBase(
        hp=60, ataque=60, defesa=60, ataque_especial=60, defesa_especial=60, velocidade=60
    )
    for nivel in range(1, balance.NIVEL_MAXIMO + 1):
        stats = calcular_stats_efetivos(base, nivel)
        assert stats.hp > stats.ataque
        assert stats.hp > stats.defesa
        assert stats.hp > stats.ataque_especial
        assert stats.hp > stats.defesa_especial
        assert stats.hp > stats.velocidade


def test_nenhum_stat_fica_abaixo_do_bonus_fixo():
    base = StatsBase(hp=0, ataque=0, defesa=0, ataque_especial=0, defesa_especial=0, velocidade=0)
    stats = calcular_stats_efetivos(base, 1)
    assert stats.ataque == balance.BONUS_STAT_FIXO
    assert stats.hp == 1 + balance.BONUS_HP_FIXO


def test_nivel_zero_e_recusado():
    with pytest.raises(NivelInvalido):
        calcular_stats_efetivos(BULBASAUR, 0)


def test_nivel_acima_do_maximo_e_recusado():
    # Invariante 7: nenhum Pokemon passa do nivel 100.
    with pytest.raises(NivelInvalido):
        calcular_stats_efetivos(BULBASAUR, balance.NIVEL_MAXIMO + 1)


def test_stat_base_negativo_e_recusado():
    base = StatsBase(
        hp=45, ataque=-1, defesa=49, ataque_especial=65, defesa_especial=65, velocidade=45
    )
    with pytest.raises(StatInvalido):
        calcular_stats_efetivos(base, 5)


# --- HP absoluto ------------------------------------------------------------


def test_hp_cheio_devolve_o_hp_efetivo_inteiro():
    assert hp_atual_absoluto(105, balance.BASE_PERCENTUAL) == 105


def test_hp_zerado_devolve_zero():
    # Nocauteado e nocauteado: o piso de HP_MINIMO_VIVO nao vale aqui.
    assert hp_atual_absoluto(105, 0) == 0


def test_porcentagem_minima_nunca_arredonda_para_zero():
    # 1% de 11 da 0,11, que arredondado seria zero: o Pokemon apareceria
    # nocauteado sem ter caido.
    assert hp_atual_absoluto(11, 1) == balance.HP_MINIMO_VIVO


@pytest.mark.parametrize("hp_efetivo", [11, 19, 45, 105, 200])
def test_qualquer_porcentagem_positiva_mantem_o_pokemon_vivo(hp_efetivo):
    """A propriedade vale para todo pct de 1 a 100, conferido aqui num laco.

    Isto ja foi um parametrize sobre `range(1, 101)`, o que rendia 500 casos
    coletados — sozinho, 41% da suite inteira do projeto. A propriedade e uma
    so e quebra nos extremos, nao no meio: multiplicar o numero de casos
    inflava o relatorio sem acrescentar confianca, e cada caso coletado custa
    tempo de coleta em toda execucao.

    O laco cobre exatamente a mesma faixa. O que se perde e o nome do pct no
    relatorio quando falha, e por isso ele vai na mensagem do assert.
    """
    for pct in range(1, balance.BASE_PERCENTUAL + 1):
        atual = hp_atual_absoluto(hp_efetivo, pct)
        assert balance.HP_MINIMO_VIVO <= atual <= hp_efetivo, (
            f"hp_efetivo={hp_efetivo}, pct={pct}, atual={atual}"
        )


def test_hp_absoluto_cresce_com_a_porcentagem():
    for menor, maior in pairwise(range(0, balance.BASE_PERCENTUAL + 1)):
        assert hp_atual_absoluto(105, maior) >= hp_atual_absoluto(105, menor)


@pytest.mark.parametrize(
    ("hp_efetivo", "pct", "esperado"),
    [
        (200, 25, 50),  # 50 exato
        (105, 84, 88),  # 88,2 -> 88
        # Empates caem para o par, como round() define. A conta e feita em
        # Fraction para que o empate seja empate de verdade, e nao o vizinho
        # que o float escolheu.
        (105, 50, 52),  # 52,5 -> 52
        (105, 10, 10),  # 10,5 -> 10
        (19, 50, 10),  # 9,5 -> 10
        (11, 50, 6),  # 5,5 -> 6
    ],
)
def test_tabela_de_hp_absoluto(hp_efetivo, pct, esperado):
    assert hp_atual_absoluto(hp_efetivo, pct) == esperado


def test_porcentagem_acima_de_cem_e_recusada():
    with pytest.raises(HpAtualInvalido):
        hp_atual_absoluto(105, balance.BASE_PERCENTUAL + 1)


def test_porcentagem_negativa_e_recusada():
    with pytest.raises(HpAtualInvalido):
        hp_atual_absoluto(105, -1)


def test_hp_efetivo_negativo_e_recusado():
    with pytest.raises(StatInvalido):
        hp_atual_absoluto(-1, 50)
