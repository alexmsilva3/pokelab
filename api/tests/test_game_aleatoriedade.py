"""O sorteio por peso compartilhado (Artigo III).

Encontros e achados de item usam a mesma funcao, e e aqui que ela e verificada
isolada: faixa, borda, entrada degenerada e estabilidade por semente.
"""

import pytest

from app.game.aleatoriedade import sortear_indice_por_peso
from app.game.erros import SorteioInvalido
from tests.geradores_falsos import GeradorRoteirizado, GeradorSemeado

PESOS = [50, 30, 20]  # acumulados 50, 80, 100

# valor de random(), indice esperado
TABELA_DE_FAIXAS = [
    (0.0, 0),
    (0.49, 0),
    (0.4999999, 0),
    (0.5, 1),  # borda: a faixa e fechada embaixo e aberta em cima
    (0.7999999, 1),
    (0.8, 2),
    (0.9999999, 2),
]


@pytest.mark.parametrize(("valor", "esperado"), TABELA_DE_FAIXAS)
def test_indice_cai_na_faixa_certa(valor, esperado):
    assert sortear_indice_por_peso(PESOS, GeradorRoteirizado(floats=[valor])) == esperado


def test_um_unico_peso_ainda_consome_a_rolagem():
    gerador = GeradorRoteirizado(floats=[0.3])

    assert sortear_indice_por_peso([7], gerador) == 0
    assert gerador.chamadas == ["random"]


def test_lista_vazia_levanta():
    with pytest.raises(SorteioInvalido):
        sortear_indice_por_peso([], GeradorRoteirizado(floats=[0.5]))


def test_peso_total_zero_levanta():
    with pytest.raises(SorteioInvalido):
        sortear_indice_por_peso([0, 0], GeradorRoteirizado(floats=[0.5]))


def test_peso_negativo_levanta():
    with pytest.raises(SorteioInvalido):
        sortear_indice_por_peso([5, -1], GeradorRoteirizado(floats=[0.5]))


def test_peso_zero_no_meio_nunca_e_escolhido():
    for passo in range(0, 1000):
        gerador = GeradorRoteirizado(floats=[passo / 1000])
        assert sortear_indice_por_peso([1, 0, 1], gerador) != 1


def test_a_distribuicao_segue_os_pesos():
    gerador = GeradorSemeado(42)
    contagem = [0, 0, 0]

    for _ in range(10_000):
        contagem[sortear_indice_por_peso(PESOS, gerador)] += 1

    assert 4_700 < contagem[0] < 5_300
    assert 2_700 < contagem[1] < 3_300
    assert 1_700 < contagem[2] < 2_300


def test_a_mesma_semente_produz_a_mesma_sequencia():
    def rodada():
        gerador = GeradorSemeado(99)
        return [sortear_indice_por_peso(PESOS, gerador) for _ in range(50)]

    assert rodada() == rodada()


def test_a_ordem_dos_pesos_muda_o_resultado():
    direto = sortear_indice_por_peso([50, 50], GeradorRoteirizado(floats=[0.6]))
    espelhado = sortear_indice_por_peso([50, 50], GeradorRoteirizado(floats=[0.4]))

    assert (direto, espelhado) == (1, 0)
