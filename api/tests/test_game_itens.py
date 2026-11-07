"""O item do seed como o dominio o ve em campo (SDD 3.1, regra 17 da spec 007).

A carga da expedicao e debitada em campo; o estoque do laboratorio nao.
"""

import pytest

from app.game.erros import ItemInvalido
from app.game.itens import (
    CategoriaDeItem,
    ItemDaMochila,
    categoria_de,
    consumir,
    da_categoria,
)

POTION = ItemDaMochila(
    item_id="potion", nome="Potion", categoria=CategoriaDeItem.CURA, potencia=20.0, quantidade=2
)
REVIVE = ItemDaMochila(
    item_id="revive",
    nome="Revive",
    categoria=CategoriaDeItem.REVIVE,
    potencia=50.0,
    quantidade=1,
)
POKE_BALL = ItemDaMochila(
    item_id="poke-ball",
    nome="Poke Ball",
    categoria=CategoriaDeItem.POKEBOLA,
    potencia=1.0,
    quantidade=5,
)


@pytest.mark.parametrize("texto", ["POKEBOLA", "CURA", "REVIVE"])
def test_categoria_do_seed_e_reconhecida(texto):
    assert categoria_de(texto).value == texto


def test_categoria_desconhecida_e_recusada():
    with pytest.raises(ItemInvalido):
        categoria_de("POCAO")


def test_potencia_de_cura_sai_em_pontos_inteiros():
    assert POTION.potencia_em_pontos == 20
    assert REVIVE.potencia_em_pontos == 50


def test_potencia_fracionaria_nao_vira_pontos_de_hp():
    estranho = ItemDaMochila(
        item_id="potion",
        nome="Potion",
        categoria=CategoriaDeItem.CURA,
        potencia=20.5,
        quantidade=1,
    )

    with pytest.raises(ItemInvalido):
        _ = estranho.potencia_em_pontos


def test_potencia_negativa_e_recusada_na_construcao():
    with pytest.raises(ItemInvalido):
        ItemDaMochila(
            item_id="potion",
            nome="Potion",
            categoria=CategoriaDeItem.CURA,
            potencia=-1.0,
            quantidade=1,
        )


def test_quantidade_negativa_e_recusada_na_construcao():
    with pytest.raises(ItemInvalido):
        ItemDaMochila(
            item_id="potion",
            nome="Potion",
            categoria=CategoriaDeItem.CURA,
            potencia=20.0,
            quantidade=-1,
        )


def test_da_categoria_filtra_e_preserva_a_ordem():
    vazia = ItemDaMochila(
        item_id="super-potion",
        nome="Super Potion",
        categoria=CategoriaDeItem.CURA,
        potencia=50.0,
        quantidade=0,
    )
    carga = (POKE_BALL, POTION, vazia, REVIVE)

    assert [item.item_id for item in da_categoria(carga, CategoriaDeItem.CURA)] == ["potion"]
    assert da_categoria(carga, CategoriaDeItem.POKEBOLA) == (POKE_BALL,)


def test_consumir_debita_uma_unidade_e_preserva_a_ordem():
    nova = consumir((POTION, REVIVE), "potion")

    assert [item.item_id for item in nova] == ["potion", "revive"]
    assert nova[0].quantidade == POTION.quantidade - 1
    assert nova[1] == REVIVE


def test_consumir_nao_altera_a_carga_recebida():
    carga = (POTION, REVIVE)

    consumir(carga, "potion")

    assert carga[0].quantidade == 2


def test_consumir_mais_do_que_ha_e_recusado():
    with pytest.raises(ItemInvalido):
        consumir((REVIVE,), "revive", 2)


def test_consumir_item_fora_da_carga_e_recusado():
    with pytest.raises(ItemInvalido):
        consumir((POTION,), "ultra-ball")


def test_disponivel_distingue_linha_zerada():
    assert POTION.disponivel is True
    assert (
        ItemDaMochila(
            item_id="potion",
            nome="Potion",
            categoria=CategoriaDeItem.CURA,
            potencia=20.0,
            quantidade=0,
        ).disponivel
        is False
    )
