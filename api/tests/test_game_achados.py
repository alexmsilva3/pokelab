"""Achados de item em campo (tarefa 7.12 do SDD, evento ITEM do relatorio).

A chance, a tabela ponderada, a quantidade por dificuldade e a conta de
economia que justifica os numeros.
"""

import pytest

from app.game import balance
from app.game.achados import AchadoInvalido, achado_apos_vitoria, quantidade_do_achado
from app.game.erros import SorteioInvalido
from tests.geradores_falsos import GeradorRoteirizado, GeradorSemeado

# Acumulados de TABELA_DE_ACHADOS: poke-ball 0..65, great-ball 65..80,
# potion 80..95, revive 95..100.
# Faixa de dificuldade que o mapa de Kanto de fato tem (data/seed/locations.json,
# de Pallet Town a Cerulean City). Nao e calibragem: e o dado que existe.
DIFICULDADE_MINIMA_DO_MAPA = 1
DIFICULDADE_MAXIMA_DO_MAPA = 6

# A banda da economia, declarada no bloco de comentario de balance.py e repetida
# no docstring de achados.py: "de 0,2 a 0,4 bola devolvida por vitoria".
RETORNO_MINIMO_DOCUMENTADO = 0.2
RETORNO_MAXIMO_DOCUMENTADO = 0.4

TABELA_DE_FAIXAS = [
    (0.0, "poke-ball"),
    (0.6499, "poke-ball"),
    (0.65, "great-ball"),
    (0.7999, "great-ball"),
    (0.8, "potion"),
    (0.9499, "potion"),
    (0.950001, "revive"),
    (0.999, "revive"),
]


@pytest.mark.parametrize(("valor", "item_esperado"), TABELA_DE_FAIXAS)
def test_item_sorteado_cai_na_faixa_certa(valor, item_esperado):
    gerador = GeradorRoteirizado(floats=[0.0, valor])

    achado = achado_apos_vitoria(1, gerador)

    assert achado is not None
    assert achado.item_id == item_esperado


def test_a_borda_e_comparada_em_aritmetica_exata():
    # O double mais proximo de 0.95 vale 0.94999999999999995559..., que e
    # MENOR que 95/100. A comparacao exata honra isso e devolve a potion; se a
    # conta corresse em ponto flutuante com outro arredondamento, a mesma
    # semente poderia cair na linha seguinte depois de uma calibragem.
    gerador = GeradorRoteirizado(floats=[0.0, 0.95])

    achado = achado_apos_vitoria(1, gerador)

    assert achado is not None
    assert achado.item_id == "potion"


def test_rolagem_igual_ou_acima_da_chance_nao_produz_achado():
    # Usar `balance.CHANCE_ITEM_POR_VITORIA` direto como valor da rolagem so
    # prova a borda quando a constante e exatamente representavel em binario
    # (0.25 e; 0.30, por exemplo, nao e -- `Fraction(0.30)` e `Fraction("0.30")`
    # diferem na casa decimal menos significativa). Uma margem acima da chance
    # testa a mesma regra (`random() >= chance` nao produz achado) sem
    # depender de como o float da calibragem arredonda.
    alem_da_chance = min(0.999999, balance.CHANCE_ITEM_POR_VITORIA + 0.0001)
    gerador = GeradorRoteirizado(floats=[alem_da_chance])

    assert achado_apos_vitoria(5, gerador) is None
    assert gerador.chamadas == ["random"]


def test_rolagem_logo_abaixo_da_chance_produz_achado():
    gerador = GeradorRoteirizado(floats=[balance.CHANCE_ITEM_POR_VITORIA - 0.0001, 0.1])

    assert achado_apos_vitoria(5, gerador) is not None


def test_achado_consome_duas_rolagens_na_ordem_fixada():
    gerador = GeradorRoteirizado(floats=[0.1, 0.1])

    achado_apos_vitoria(1, gerador)

    assert gerador.chamadas == ["random", "random"]


# nivel de dificuldade do local, quantidade esperada
TABELA_DE_QUANTIDADE = [(0, 1), (1, 1), (3, 1), (4, 2), (5, 2), (7, 2), (8, 3), (10, 3)]


@pytest.mark.parametrize(("dificuldade", "esperado"), TABELA_DE_QUANTIDADE)
def test_quantidade_cresce_em_degraus_com_a_dificuldade(dificuldade, esperado):
    assert quantidade_do_achado(dificuldade) == esperado


def test_quantidade_entra_no_achado():
    gerador = GeradorRoteirizado(floats=[0.0, 0.0])

    achado = achado_apos_vitoria(5, gerador)

    assert achado is not None
    assert achado.quantidade == 2


def test_dificuldade_negativa_e_recusada():
    with pytest.raises(AchadoInvalido):
        quantidade_do_achado(-1)
    with pytest.raises(AchadoInvalido):
        achado_apos_vitoria(-1, GeradorRoteirizado(floats=[0.0, 0.0]))


def test_a_mesma_semente_produz_o_mesmo_achado():
    def rodada():
        gerador = GeradorSemeado(777)
        return [achado_apos_vitoria(5, gerador) for _ in range(20)]

    assert rodada() == rodada()


def test_tabela_de_achados_tem_peso_valido():
    pesos = [peso for _, peso in balance.TABELA_DE_ACHADOS]

    assert balance.TABELA_DE_ACHADOS
    assert all(peso > 0 for peso in pesos)
    # Os pesos somam 100 de proposito, para se lerem como porcentagem.
    assert sum(pesos) == 100


def _bolas_por_vitoria(nivel_dificuldade: int) -> float:
    """O retorno esperado em Pokebolas por vitoria, num local desta dificuldade.

    E a conta que o bloco de comentario de balance.py documenta: a chance de
    haver achado, vezes a fatia da tabela que e bola, vezes quantas vem.
    """
    pesos = dict(balance.TABELA_DE_ACHADOS)
    peso_das_bolas = pesos["poke-ball"] + pesos["great-ball"]
    return (
        balance.CHANCE_ITEM_POR_VITORIA
        * (peso_das_bolas / sum(pesos.values()))
        * quantidade_do_achado(nivel_dificuldade)
    )


def test_a_expedicao_nao_devolve_mais_bola_do_que_consome():
    # A regra existe para que a expedicao se pague PARCIALMENTE. Uma tentativa
    # de captura gasta uma bola por vitoria; o retorno esperado por vitoria,
    # mesmo no local mais dificil do mapa, tem de ficar abaixo disso.
    assert _bolas_por_vitoria(DIFICULDADE_MAXIMA_DO_MAPA) < 1


def test_o_retorno_em_bolas_fica_dentro_da_banda_documentada():
    """Prende a BANDA da economia, nao o valor de CHANCE_ITEM_POR_VITORIA.

    O Artigo IX probe fixar constante de calibragem num teste, e com razao: um
    teste que exigisse `CHANCE_ITEM_POR_VITORIA == 0.25` quebraria em toda
    calibragem legitima da Fase 9 sem apontar defeito nenhum.

    So que a folga virou buraco. O unico guarda numerico que existia era
    `bolas_por_vitoria < 1`, que so dispara com a chance em 0,4167 — 67% acima
    da calibragem atual. Uma mutacao de 0,25 para 0,30 passava a suite inteira
    em verde, rompendo em silencio o teto de 35% da mochila que balance.py e o
    docstring de achados.py declaram por escrito, e com ele a premissa de que a
    loja da Fase 8 tem para que existir.

    A saida e prender o CONTRATO em vez do numero: a banda de 0,2 a 0,4 bola
    por vitoria esta escrita nos dois lugares, e qualquer calibragem que a
    respeite passa aqui. Se a Fase 9 decidir mudar a banda, este teste quebra —
    e e o que se quer, porque os dois comentarios precisam mudar junto.
    """
    retornos = [
        _bolas_por_vitoria(dificuldade)
        for dificuldade in range(DIFICULDADE_MINIMA_DO_MAPA, DIFICULDADE_MAXIMA_DO_MAPA + 1)
    ]

    assert min(retornos) >= RETORNO_MINIMO_DOCUMENTADO
    assert max(retornos) <= RETORNO_MAXIMO_DOCUMENTADO


def test_tabela_vazia_levantaria_em_vez_de_devolver_item_errado(monkeypatch):
    monkeypatch.setattr(balance, "TABELA_DE_ACHADOS", ())

    with pytest.raises(SorteioInvalido):
        achado_apos_vitoria(1, GeradorRoteirizado(floats=[0.0]))
