"""Captura (SDD 4.6, criterios 6, 7 e 8 da spec 007).

Tabela de probabilidades conferida a mao, os dois limites do clamp, o caso do
time muito abaixo do selvagem e a conta de slots de bagagem.
"""

from fractions import Fraction

import pytest

from app.game import balance
from app.game.capture import (
    contar_pokebolas,
    escolher_pokebola,
    nivel_medio_do_time,
    probabilidade_de_captura,
    slots_de_captura,
)
from app.game.erros import NivelInvalido, TaxaDeCapturaInvalida
from app.game.itens import CategoriaDeItem, ItemDaMochila
from app.game.team import TamanhoDeTimeInvalido, TimeCheio


def bola(item_id="poke-ball", potencia=1.0, quantidade=1):
    return ItemDaMochila(
        item_id=item_id,
        nome=item_id,
        categoria=CategoriaDeItem.POKEBOLA,
        potencia=potencia,
        quantidade=quantidade,
    )


POTION = ItemDaMochila(
    item_id="potion", nome="Potion", categoria=CategoriaDeItem.CURA, potencia=20.0, quantidade=2
)


# taxa, multiplicador, nivel medio do time, nivel selvagem, p esperado
# Conta a mao: (taxa / 255) * bola * (1 + (medio - selvagem) * 0.02) * 1.0
TABELA_DE_CAPTURA = [
    # Caterpie (taxa 255) com Poke Ball, time no mesmo nivel: 1.0 -> teto 0.90
    (255, 1.0, 5, 5, 0.9),
    # Pidgey (taxa 255) com time 10 niveis acima: tambem no teto
    (255, 1.0, 15, 5, 0.9),
    # Rattata (taxa 127) com Poke Ball, mesmo nivel: 127/255 = 0.498
    (127, 1.0, 5, 5, 0.498),
    # a mesma Rattata com Great Ball: 0.498 * 1.5 = 0.7471
    (127, 1.5, 5, 5, 0.7471),
    # Abra (taxa 200), time 5 niveis abaixo: 0.7843 * 0.9 = 0.7059
    (200, 1.0, 10, 15, 0.7059),
    # Dragonair (taxa 45) com Ultra Ball, mesmo nivel: 0.1765 * 2 = 0.3529
    (45, 2.0, 30, 30, 0.3529),
    # Articuno (taxa 3) com Poke Ball: 0.0118 -> abaixo do piso, vira 0.05
    (3, 1.0, 50, 50, 0.05),
]


@pytest.mark.parametrize(("taxa", "bola_mult", "medio", "selvagem", "esperado"), TABELA_DE_CAPTURA)
def test_probabilidade_de_captura_bate_com_a_tabela(taxa, bola_mult, medio, selvagem, esperado):
    assert probabilidade_de_captura(taxa, bola_mult, medio, selvagem) == esperado


def test_probabilidade_respeita_o_teto():
    assert probabilidade_de_captura(255, 2.0, 100, 1) == balance.P_CAPTURA_MAXIMA


def test_probabilidade_respeita_o_piso():
    assert probabilidade_de_captura(3, 1.0, 1, 100) == balance.P_CAPTURA_MINIMA


def test_time_muito_abaixo_do_selvagem_cai_no_piso_e_nao_em_valor_negativo():
    # Mais de 50 niveis de diferenca torna o fator de nivel negativo
    # (1 + (-60) * 0.02 = -0.2). O clamp e quem salva: o resultado e o piso,
    # nunca um numero negativo.
    p = probabilidade_de_captura(255, 1.0, 5, 65)

    assert p == balance.P_CAPTURA_MINIMA
    assert p > 0


def test_captura_nunca_piora_quando_o_time_sobe_de_nivel():
    # O piso devolve a monotonicidade que o fator negativo tiraria.
    anteriores = [probabilidade_de_captura(255, 1.0, nivel, 60) for nivel in range(1, 101)]

    assert anteriores == sorted(anteriores)


@pytest.mark.parametrize("nivel_medio", [Fraction(19, 3), 6.5, 7])
def test_nivel_medio_aceita_media_fracionaria(nivel_medio):
    assert 0 < probabilidade_de_captura(127, 1.0, nivel_medio, 5) <= 1


def test_nivel_medio_do_time_e_exato():
    assert nivel_medio_do_time([5, 6, 8]) == Fraction(19, 3)


def test_nivel_medio_de_time_vazio_e_recusado():
    with pytest.raises(NivelInvalido):
        nivel_medio_do_time([])


def test_probabilidade_e_deterministica():
    primeira = probabilidade_de_captura(127, 1.5, Fraction(19, 3), 7)
    segunda = probabilidade_de_captura(127, 1.5, Fraction(19, 3), 7)

    assert primeira == segunda


@pytest.mark.parametrize("taxa", [-1, balance.TAXA_CAPTURA_MAXIMA + 1])
def test_taxa_de_captura_fora_da_faixa_e_recusada(taxa):
    with pytest.raises(TaxaDeCapturaInvalida):
        probabilidade_de_captura(taxa, 1.0, 5, 5)


@pytest.mark.parametrize("multiplicador", [0.0, -1.0])
def test_multiplicador_de_bola_nao_positivo_e_recusado(multiplicador):
    with pytest.raises(TaxaDeCapturaInvalida):
        probabilidade_de_captura(127, multiplicador, 5, 5)


@pytest.mark.parametrize("nivel", [0, balance.NIVEL_MAXIMO + 1])
def test_nivel_selvagem_fora_da_faixa_e_recusado(nivel):
    with pytest.raises(NivelInvalido):
        probabilidade_de_captura(127, 1.0, 5, nivel)


# --- Slots de bagagem (invariante 11) ---------------------------------------

# bolas na carga, tamanho do time, slots esperados
TABELA_DE_SLOTS = [
    (10, 3, 3),  # time cheio: sobram 3 lugares, e as bolas nao sao o gargalo
    (10, 1, 5),  # time de um: 5 lugares
    (10, 0, 6),  # treinador sem time nao sai em expedicao, mas a conta e esta
    (0, 1, 0),  # sem bola nao ha captura, criterio 8 da spec 007
    (2, 1, 2),  # a carga e o gargalo
    (5, 3, 3),  # a bagagem e o gargalo
]


@pytest.mark.parametrize(("bolas", "tamanho", "esperado"), TABELA_DE_SLOTS)
def test_slots_de_captura_bate_com_a_tabela(bolas, tamanho, esperado):
    assert slots_de_captura(bolas, tamanho) == esperado


def test_slots_nunca_sao_negativos():
    for bolas in range(0, 12):
        for tamanho in range(0, balance.TAMANHO_MAXIMO_TIME + 1):
            assert slots_de_captura(bolas, tamanho) >= 0


def test_carga_de_bolas_negativa_e_recusada():
    with pytest.raises(TaxaDeCapturaInvalida):
        slots_de_captura(-1, 1)


def test_time_negativo_e_recusado_pela_capacidade_de_bagagem():
    with pytest.raises(TamanhoDeTimeInvalido):
        slots_de_captura(5, -1)


def test_time_maior_que_o_maximo_e_recusado():
    with pytest.raises(TimeCheio):
        slots_de_captura(5, balance.TAMANHO_MAXIMO_TIME + 1)


# --- Escolha da bola --------------------------------------------------------


def test_contar_pokebolas_soma_todos_os_tipos():
    carga = [bola("poke-ball", 1.0, 3), bola("ultra-ball", 2.0, 2), POTION]

    assert contar_pokebolas(carga) == 5


def test_escolher_pokebola_gasta_a_mais_fraca_primeiro():
    carga = [bola("ultra-ball", 2.0, 1), bola("poke-ball", 1.0, 1), POTION]

    escolhida = escolher_pokebola(carga)

    assert escolhida is not None
    assert escolhida.item_id == "poke-ball"


def test_escolher_pokebola_ignora_linha_zerada():
    carga = [bola("poke-ball", 1.0, 0), bola("great-ball", 1.5, 1)]

    escolhida = escolher_pokebola(carga)

    assert escolhida is not None
    assert escolhida.item_id == "great-ball"


def test_escolher_pokebola_sem_bola_devolve_nada():
    assert escolher_pokebola([POTION]) is None
    assert escolher_pokebola([]) is None
