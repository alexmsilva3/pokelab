"""Curvas de crescimento (SDD 4.1).

Tabela de valores conhecidos, consistencia entre os dois sentidos da conversao
e os invariantes que a Fase 7 vai depender.
"""

from itertools import pairwise

import pytest

from app.game import balance
from app.game.erros import CurvaDesconhecida, ExperienciaInvalida, NivelInvalido
from app.game.experience import (
    CurvaCrescimento,
    curva_de,
    experiencia_para_o_proximo_nivel,
    experiencia_total_para_nivel,
    nivel_para_experiencia,
    tabela_da_curva,
)

# curva, nivel, experiencia acumulada esperada
TABELA_CONHECIDA = [
    ("rapida", 1, 0),
    ("rapida", 5, 100),
    ("rapida", 50, 100_000),
    ("rapida", 100, 800_000),
    ("media_rapida", 1, 0),
    ("media_rapida", 5, 125),
    ("media_rapida", 50, 125_000),
    ("media_rapida", 100, 1_000_000),
    ("media_lenta", 1, 0),
    ("media_lenta", 5, 135),
    ("media_lenta", 50, 117_360),
    ("media_lenta", 100, 1_059_860),
    ("lenta", 1, 0),
    ("lenta", 5, 156),
    ("lenta", 50, 156_250),
    ("lenta", 100, 1_250_000),
]


@pytest.mark.parametrize(("curva", "nivel", "esperado"), TABELA_CONHECIDA)
def test_experiencia_total_bate_com_a_tabela_do_sdd(curva, nivel, esperado):
    assert experiencia_total_para_nivel(curva, nivel) == esperado


@pytest.mark.parametrize("curva", list(CurvaCrescimento))
def test_nivel_1_nao_custa_experiencia_em_nenhuma_curva(curva):
    assert experiencia_total_para_nivel(curva, 1) == 0


@pytest.mark.parametrize("curva", list(CurvaCrescimento))
def test_curva_nunca_devolve_experiencia_negativa(curva):
    for nivel in range(1, balance.NIVEL_MAXIMO + 1):
        assert experiencia_total_para_nivel(curva, nivel) >= 0


def test_media_lenta_nao_devolve_negativo_apesar_do_polinomio():
    # 1.2n^3 - 15n^2 + 100n - 140 vale -53.8 no nivel 1: o piso em zero existe
    # para esse caso, e o nivel 2 ja e o primeiro valor positivo do polinomio.
    assert experiencia_total_para_nivel("media_lenta", 1) == 0
    assert experiencia_total_para_nivel("media_lenta", 2) == 9
    assert all(valor >= 0 for valor in tabela_da_curva("media_lenta"))


@pytest.mark.parametrize("curva", list(CurvaCrescimento))
def test_curva_e_estritamente_crescente(curva):
    tabela = tabela_da_curva(curva)
    assert all(anterior < proximo for anterior, proximo in pairwise(tabela))


@pytest.mark.parametrize("curva", list(CurvaCrescimento))
def test_os_dois_sentidos_sao_consistentes(curva):
    for nivel in range(1, balance.NIVEL_MAXIMO + 1):
        total = experiencia_total_para_nivel(curva, nivel)
        assert nivel_para_experiencia(curva, total) == nivel


@pytest.mark.parametrize("curva", list(CurvaCrescimento))
def test_um_ponto_antes_do_proximo_nivel_ainda_e_o_nivel_atual(curva):
    for nivel in range(2, balance.NIVEL_MAXIMO + 1):
        total = experiencia_total_para_nivel(curva, nivel)
        assert nivel_para_experiencia(curva, total - 1) == nivel - 1


@pytest.mark.parametrize("curva", list(CurvaCrescimento))
def test_nivel_satura_no_maximo(curva):
    total_maximo = experiencia_total_para_nivel(curva, balance.NIVEL_MAXIMO)
    assert nivel_para_experiencia(curva, total_maximo * 1000) == balance.NIVEL_MAXIMO


@pytest.mark.parametrize("curva", list(CurvaCrescimento))
def test_experiencia_zero_e_nivel_1(curva):
    assert nivel_para_experiencia(curva, 0) == 1


@pytest.mark.parametrize("curva", list(CurvaCrescimento))
def test_quanto_falta_para_o_proximo_nivel(curva):
    total_5 = experiencia_total_para_nivel(curva, 5)
    total_6 = experiencia_total_para_nivel(curva, 6)
    assert experiencia_para_o_proximo_nivel(curva, total_5) == total_6 - total_5
    no_teto = experiencia_total_para_nivel(curva, balance.NIVEL_MAXIMO)
    assert experiencia_para_o_proximo_nivel(curva, no_teto) == 0


def test_mesma_entrada_devolve_sempre_o_mesmo_valor():
    primeira = [experiencia_total_para_nivel("media_lenta", n) for n in range(1, 101)]
    segunda = [experiencia_total_para_nivel("media_lenta", n) for n in range(1, 101)]
    assert primeira == segunda


def test_curva_de_aceita_texto_do_seed():
    assert curva_de("media_lenta") is CurvaCrescimento.MEDIA_LENTA
    assert curva_de(CurvaCrescimento.RAPIDA) is CurvaCrescimento.RAPIDA


def test_curva_desconhecida_e_recusada():
    with pytest.raises(CurvaDesconhecida, match="desconhecida"):
        experiencia_total_para_nivel("lentissima", 5)


@pytest.mark.parametrize("nivel", [0, -1, balance.NIVEL_MAXIMO + 1])
def test_nivel_fora_da_faixa_e_recusado(nivel):
    with pytest.raises(NivelInvalido, match="fora da faixa"):
        experiencia_total_para_nivel("rapida", nivel)


def test_experiencia_negativa_e_recusada():
    with pytest.raises(ExperienciaInvalida, match="negativa"):
        nivel_para_experiencia("rapida", -1)
