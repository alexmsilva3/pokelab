"""Evolucao por nivel (SDD 4.1, criterio 11 da spec 007).

Cadeia de um e de dois saltos, o que nao evolui, e o que o catalogo quebrado
tem de levantar.
"""

import pytest

from app.game import balance
from app.game.erros import CatalogoInvalido, NivelInvalido
from app.game.evolucao import EspecieNoCatalogo, evolucoes_apos

# A linha de Bulbasaur do seed: 1 -> 2 no nivel 16, 2 -> 3 no nivel 32.
CATALOGO = {
    1: EspecieNoCatalogo(id=1, nome="Bulbasaur", evolui_para_id=2, evolui_em_nivel=16),
    2: EspecieNoCatalogo(id=2, nome="Ivysaur", evolui_para_id=3, evolui_em_nivel=32),
    3: EspecieNoCatalogo(id=3, nome="Venusaur"),
    129: EspecieNoCatalogo(id=129, nome="Magikarp", evolui_para_id=130, evolui_em_nivel=20),
    130: EspecieNoCatalogo(id=130, nome="Gyarados"),
}

# especie, nivel alcancado, nomes esperados na ordem
TABELA_DE_CADEIAS = [
    (1, 5, []),
    (1, 15, []),
    (1, 16, ["Ivysaur"]),
    (1, 31, ["Ivysaur"]),
    (1, 32, ["Ivysaur", "Venusaur"]),
    (1, 33, ["Ivysaur", "Venusaur"]),
    (2, 32, ["Venusaur"]),
    (3, 100, []),
    (129, 19, []),
    (129, 20, ["Gyarados"]),
]


@pytest.mark.parametrize(("especie", "nivel", "esperado"), TABELA_DE_CADEIAS)
def test_cadeia_de_evolucao_bate_com_a_tabela(especie, nivel, esperado):
    cadeia = evolucoes_apos(especie, nivel, CATALOGO)

    assert [elo.nome for elo in cadeia] == esperado


def test_salto_de_dois_niveis_evolui_duas_vezes_numa_so_aplicacao():
    # Bulbasaur que salta do 15 ao 33 numa expedicao vira Venusaur, com dois
    # eventos: esconder Ivysaur faria a Pokedex pular um registro.
    cadeia = evolucoes_apos(1, 33, CATALOGO)

    assert [elo.id for elo in cadeia] == [2, 3]


def test_evolucao_e_idempotente_na_especie_resultante():
    cadeia = evolucoes_apos(1, 33, CATALOGO)

    assert evolucoes_apos(cadeia[-1].id, 33, CATALOGO) == ()


def test_evolucao_e_deterministica():
    assert evolucoes_apos(1, 33, CATALOGO) == evolucoes_apos(1, 33, CATALOGO)


def test_ciclo_no_catalogo_levanta_em_vez_de_girar():
    ciclico = {
        10: EspecieNoCatalogo(id=10, nome="Alfa", evolui_para_id=11, evolui_em_nivel=5),
        11: EspecieNoCatalogo(id=11, nome="Beta", evolui_para_id=10, evolui_em_nivel=5),
    }

    with pytest.raises(CatalogoInvalido) as erro:
        evolucoes_apos(10, 50, ciclico)

    assert str(balance.EVOLUCOES_MAXIMAS_POR_EXPEDICAO) in str(erro.value)


def test_especie_fora_do_catalogo_levanta():
    with pytest.raises(CatalogoInvalido):
        evolucoes_apos(999, 10, CATALOGO)


def test_evolucao_que_aponta_para_especie_ausente_levanta():
    quebrado = {1: EspecieNoCatalogo(id=1, nome="Bulbasaur", evolui_para_id=2, evolui_em_nivel=16)}

    with pytest.raises(CatalogoInvalido):
        evolucoes_apos(1, 20, quebrado)


def test_elo_sem_nivel_de_evolucao_levanta():
    quebrado = {1: EspecieNoCatalogo(id=1, nome="Bulbasaur", evolui_para_id=2)}

    with pytest.raises(CatalogoInvalido):
        evolucoes_apos(1, 20, quebrado)


def test_nivel_de_evolucao_fora_da_faixa_levanta():
    quebrado = {
        1: EspecieNoCatalogo(id=1, nome="Bulbasaur", evolui_para_id=2, evolui_em_nivel=0),
        2: EspecieNoCatalogo(id=2, nome="Ivysaur"),
    }

    with pytest.raises(CatalogoInvalido):
        evolucoes_apos(1, 20, quebrado)


@pytest.mark.parametrize("nivel", [0, balance.NIVEL_MAXIMO + 1])
def test_nivel_fora_da_faixa_e_recusado(nivel):
    with pytest.raises(NivelInvalido):
        evolucoes_apos(1, nivel, CATALOGO)
