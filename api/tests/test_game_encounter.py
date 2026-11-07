"""Sorteio de encontros (SDD 4.5, criterio 3 da spec 007).

O sorteio por peso e verificado com gerador roteirizado, faixa por faixa e
borda por borda: e a unica forma de provar que a mesma semente escolhe sempre
a mesma especie.
"""

import pytest

from app.game import balance
from app.game.encounter import (
    EncontroInvalido,
    LinhaDeEncontro,
    ordenar_linhas,
    quantidade_de_encontros,
    sortear_especie,
    sortear_nivel,
)
from app.game.erros import NivelInvalido, SorteioInvalido
from tests.geradores_falsos import GeradorRoteirizado, GeradorSemeado

# A tabela da Route 1 do seed, em ordem canonica (especie_id crescente).
# Acumulados: Pidgey 0..50, Rattata 50..80, Caterpie 80..100.
ROUTE_1 = (
    LinhaDeEncontro(especie_id=16, peso=50, nivel_min=2, nivel_max=4),
    LinhaDeEncontro(especie_id=19, peso=30, nivel_min=2, nivel_max=4),
    LinhaDeEncontro(especie_id=10, peso=20, nivel_min=3, nivel_max=5),
)

# valor de random(), especie esperada. Inclui as duas bordas de cada acumulado.
TABELA_DE_FAIXAS = [
    (0.0, 16),
    (0.01, 16),
    (0.4999, 16),
    (0.5, 19),  # borda: alvo igual ao acumulado cai na linha SEGUINTE
    (0.79, 19),
    (0.7999, 19),
    (0.8, 10),  # segunda borda
    (0.99, 10),
    (0.999999, 10),
]


@pytest.mark.parametrize(("valor", "especie_esperada"), TABELA_DE_FAIXAS)
def test_sorteio_por_peso_cai_na_faixa_certa(valor, especie_esperada):
    gerador = GeradorRoteirizado(floats=[valor])

    assert sortear_especie(ROUTE_1, gerador).especie_id == especie_esperada


def test_sorteio_consome_exatamente_uma_rolagem():
    gerador = GeradorRoteirizado(floats=[0.1])

    sortear_especie(ROUTE_1, gerador)

    assert gerador.chamadas == ["random"]


def test_linha_de_peso_zero_nunca_e_sorteada():
    tabela = (
        LinhaDeEncontro(especie_id=1, peso=0, nivel_min=2, nivel_max=4),
        LinhaDeEncontro(especie_id=2, peso=1, nivel_min=2, nivel_max=4),
    )

    for passo in range(0, 100):
        gerador = GeradorRoteirizado(floats=[passo / 100])
        assert sortear_especie(tabela, gerador).especie_id == 2


def test_tabela_vazia_levanta_em_vez_de_devolver_nada():
    # Decisao: um local sem tabela de encontros nao e destino possivel, e
    # devolver None produziria um relatorio vazio sem explicacao.
    with pytest.raises(SorteioInvalido):
        sortear_especie((), GeradorRoteirizado(floats=[0.5]))


def test_peso_total_zero_levanta():
    tabela = (
        LinhaDeEncontro(especie_id=1, peso=0, nivel_min=2, nivel_max=4),
        LinhaDeEncontro(especie_id=2, peso=0, nivel_min=2, nivel_max=4),
    )

    with pytest.raises(SorteioInvalido):
        sortear_especie(tabela, GeradorRoteirizado(floats=[0.5]))


def test_peso_negativo_e_recusado_na_construcao_da_linha():
    with pytest.raises(EncontroInvalido):
        LinhaDeEncontro(especie_id=1, peso=-1, nivel_min=2, nivel_max=4)


def test_faixa_de_nivel_invertida_e_recusada():
    with pytest.raises(EncontroInvalido):
        LinhaDeEncontro(especie_id=1, peso=10, nivel_min=9, nivel_max=4)


@pytest.mark.parametrize(("minimo", "maximo"), [(0, 4), (2, balance.NIVEL_MAXIMO + 1)])
def test_faixa_de_nivel_fora_da_escala_e_recusada(minimo, maximo):
    with pytest.raises(NivelInvalido):
        LinhaDeEncontro(especie_id=1, peso=10, nivel_min=minimo, nivel_max=maximo)


def test_ordem_canonica_e_por_especie_id_crescente():
    assert [linha.especie_id for linha in ordenar_linhas(ROUTE_1)] == [10, 16, 19]


def test_a_ordem_das_linhas_muda_o_resultado_e_por_isso_e_contrato():
    direta = sortear_especie(ROUTE_1, GeradorRoteirizado(floats=[0.6]))
    invertida = sortear_especie(tuple(reversed(ROUTE_1)), GeradorRoteirizado(floats=[0.6]))

    assert direta.especie_id != invertida.especie_id


# --- Nivel do selvagem ------------------------------------------------------


def test_sortear_nivel_usa_a_faixa_da_linha_com_os_extremos_incluidos():
    linha = ROUTE_1[0]
    gerador = GeradorRoteirizado(inteiros=[4])

    assert sortear_nivel(linha, gerador) == 4
    assert gerador.chamadas == ["randint(2,4)"]


def test_sortear_nivel_consome_rolagem_mesmo_com_faixa_de_um_nivel_so():
    linha = LinhaDeEncontro(especie_id=1, peso=1, nivel_min=7, nivel_max=7)
    gerador = GeradorRoteirizado(inteiros=[7])

    assert sortear_nivel(linha, gerador) == 7
    assert gerador.chamadas == ["randint(7,7)"]


# --- Quantidade de encontros ------------------------------------------------

# encontros_base, variacao sorteada, quantidade esperada
TABELA_DE_QUANTIDADE = [
    (2, -1, 1),
    (2, 0, 2),
    (2, 1, 3),
    (7, -1, 6),
    (1, -1, balance.ENCONTROS_MINIMOS),
    (0, -1, balance.ENCONTROS_MINIMOS),
    (0, 1, 1),
]


@pytest.mark.parametrize(("base", "variacao", "esperado"), TABELA_DE_QUANTIDADE)
def test_quantidade_de_encontros_bate_com_a_tabela(base, variacao, esperado):
    gerador = GeradorRoteirizado(inteiros=[variacao])

    assert quantidade_de_encontros(base, gerador) == esperado


def test_quantidade_nunca_fica_abaixo_do_minimo():
    for base in range(0, 10):
        for variacao in (-balance.VARIACAO_ENCONTROS, 0, balance.VARIACAO_ENCONTROS):
            gerador = GeradorRoteirizado(inteiros=[variacao])
            assert quantidade_de_encontros(base, gerador) >= balance.ENCONTROS_MINIMOS


def test_encontros_base_negativo_e_recusado():
    with pytest.raises(EncontroInvalido):
        quantidade_de_encontros(-1, GeradorRoteirizado(inteiros=[0]))


# --- Determinismo (Artigo III) ----------------------------------------------


def _rodada(semente):
    gerador = GeradorSemeado(semente)
    quantidade = quantidade_de_encontros(5, gerador)
    saida = [quantidade]
    for _ in range(quantidade):
        linha = sortear_especie(ROUTE_1, gerador)
        saida.append((linha.especie_id, sortear_nivel(linha, gerador)))
    return saida


def test_a_mesma_semente_produz_os_mesmos_encontros():
    assert _rodada(20261106) == _rodada(20261106)


def test_sementes_diferentes_produzem_encontros_diferentes():
    assert _rodada(1) != _rodada(2)
