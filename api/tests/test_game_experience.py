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
    aplicar_experiencia,
    curva_de,
    experiencia_maxima,
    experiencia_para_o_proximo_nivel,
    experiencia_total_para_nivel,
    nivel_para_experiencia,
    progresso_no_nivel,
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


# --- Aplicacao do ganho (Fase 7, criterios 9, 10 e 12 da spec 007) ---------


def _exp_de(curva, nivel):
    return experiencia_total_para_nivel(curva, nivel)


# curva, nivel inicial, ganho, nivel esperado, niveis ganhos esperados
TABELA_DE_GANHO = [
    ("media_rapida", 5, 0, 5, 0),  # ganho zero nao mexe em nada
    ("media_rapida", 5, 90, 5, 0),  # falta 91 para o nivel 6: nao sobe
    ("media_rapida", 5, 91, 6, 1),  # exatamente o necessario: sobe um
    ("media_rapida", 5, 1_000, 10, 5),  # expedicao longa sobe varios de uma vez
    ("rapida", 5, 100_000 - 100, 50, 45),
    ("lenta", 10, 0, 10, 0),
    ("media_lenta", 15, 1, 15, 0),
]


@pytest.mark.parametrize(
    ("curva", "nivel", "ganho", "nivel_esperado", "niveis_ganhos"), TABELA_DE_GANHO
)
def test_aplicar_experiencia_bate_com_a_tabela(curva, nivel, ganho, nivel_esperado, niveis_ganhos):
    resultado = aplicar_experiencia(curva, nivel, _exp_de(curva, nivel), ganho)

    assert resultado.nivel_antes == nivel
    assert resultado.nivel_depois == nivel_esperado
    assert resultado.niveis_ganhos == niveis_ganhos
    assert resultado.subiu is (niveis_ganhos > 0)


def test_aplicar_experiencia_soma_o_ganho_a_experiencia_gravada():
    inicial = _exp_de("media_rapida", 5)
    resultado = aplicar_experiencia("media_rapida", 5, inicial, 40)

    assert resultado.experiencia_depois == inicial + 40
    assert resultado.experiencia_aplicada == 40


@pytest.mark.parametrize("curva", list(CurvaCrescimento))
def test_ganho_absurdo_para_no_nivel_maximo_com_a_experiencia_exata(curva):
    # Criterio 12 da spec 007: o teto e duro e o excedente e descartado.
    teto = _exp_de(curva, balance.NIVEL_MAXIMO)
    resultado = aplicar_experiencia(curva, 50, _exp_de(curva, 50), 10**9)

    assert resultado.nivel_depois == balance.NIVEL_MAXIMO
    assert resultado.experiencia_depois == teto


@pytest.mark.parametrize("curva", list(CurvaCrescimento))
def test_no_nivel_maximo_mais_experiencia_nao_produz_evento_falso(curva):
    teto = _exp_de(curva, balance.NIVEL_MAXIMO)
    resultado = aplicar_experiencia(curva, balance.NIVEL_MAXIMO, teto, 500_000)

    assert resultado.nivel_antes == resultado.nivel_depois == balance.NIVEL_MAXIMO
    assert resultado.niveis_ganhos == 0
    assert resultado.subiu is False
    assert resultado.experiencia_depois == teto
    assert resultado.experiencia_aplicada == 0


def test_aplicar_experiencia_e_deterministica():
    primeira = aplicar_experiencia("lenta", 12, _exp_de("lenta", 12), 7_777)
    segunda = aplicar_experiencia("lenta", 12, _exp_de("lenta", 12), 7_777)

    assert primeira == segunda


def test_ganho_negativo_e_recusado():
    with pytest.raises(ExperienciaInvalida):
        aplicar_experiencia("rapida", 5, _exp_de("rapida", 5), -1)


def test_experiencia_negativa_e_recusada_na_aplicacao():
    with pytest.raises(ExperienciaInvalida):
        aplicar_experiencia("rapida", 5, -10, 100)


def test_nivel_fora_da_faixa_e_recusado_na_aplicacao():
    with pytest.raises(NivelInvalido):
        aplicar_experiencia("rapida", balance.NIVEL_MAXIMO + 1, 0, 100)


def test_nivel_que_nao_corresponde_a_experiencia_e_recusado():
    # Nivel 50 com a experiencia de um nivel 5: dado corrompido, nao jogada.
    with pytest.raises(ExperienciaInvalida):
        aplicar_experiencia("media_rapida", 50, _exp_de("media_rapida", 5), 10)


def test_experiencia_maxima_e_o_topo_da_tabela():
    for curva in CurvaCrescimento:
        assert experiencia_maxima(curva) == tabela_da_curva(curva)[-1]


# --- Progresso dentro do nivel (barra da ficha) ------------------------------
# A barra precisa de uma fracao, e fracao exige numerador e denominador. O
# contrato antigo so mandava o que FALTA, e faltar 44 e muito ou pouco conforme
# o degrau custe 60 ou 6000.


def test_progresso_no_piso_do_nivel_e_zero():
    curva = CurvaCrescimento.MEDIA_RAPIDA
    piso = experiencia_total_para_nivel(curva, 10)

    progresso = progresso_no_nivel(curva, piso)

    assert progresso.vencida == 0
    assert progresso.fracao == 0.0


def test_progresso_logo_antes_do_proximo_nivel_e_quase_cheio():
    curva = CurvaCrescimento.MEDIA_RAPIDA
    teto = experiencia_total_para_nivel(curva, 11)

    progresso = progresso_no_nivel(curva, teto - 1)

    assert progresso.vencida == progresso.tamanho - 1
    assert 0.9 < progresso.fracao < 1.0


def test_vencida_mais_o_que_falta_fecha_o_tamanho_do_nivel():
    # A soma das duas leituras tem de fechar o degrau: e o mesmo intervalo
    # contado de dois lados, e divergir significaria uma das duas mentindo.
    curva = CurvaCrescimento.LENTA
    for experiencia in (0, 500, 12_345, 400_000):
        progresso = progresso_no_nivel(curva, experiencia)
        falta = experiencia_para_o_proximo_nivel(curva, experiencia)

        assert progresso.vencida + falta == progresso.tamanho


def test_no_nivel_maximo_o_degrau_tem_tamanho_zero_e_a_barra_enche():
    curva = CurvaCrescimento.RAPIDA
    teto = experiencia_total_para_nivel(curva, balance.NIVEL_MAXIMO)

    progresso = progresso_no_nivel(curva, teto)

    assert progresso.tamanho == 0
    # Cheia e a leitura honesta: o Pokemon chegou. Vazia diria o contrario.
    assert progresso.fracao == 1.0


def test_a_fracao_nunca_sai_de_zero_a_um():
    for curva in CurvaCrescimento:
        for experiencia in (0, 1, 999, 50_000, experiencia_maxima(curva)):
            fracao = progresso_no_nivel(curva, experiencia).fracao

            assert 0.0 <= fracao <= 1.0


def test_experiencia_negativa_e_recusada_no_progresso():
    with pytest.raises(ExperienciaInvalida):
        progresso_no_nivel(CurvaCrescimento.MEDIA_RAPIDA, -1)
