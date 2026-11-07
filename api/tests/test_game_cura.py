"""Cura em campo (SDD 4.5, criterios 15 e 16 da spec 007).

Escolha do item mais barato que resolve, prioridade do revive, teto de 100 e
os casos em que nao ha o que gastar.
"""

import pytest

from app.game import balance
from app.game.cura import aplicar_cura, escolher_cura, ha_nocauteado, ha_o_que_curar
from app.game.erros import ItemInvalido
from app.game.itens import CategoriaDeItem, ItemDaMochila
from app.game.power import PokemonNoTime

POTION = ItemDaMochila(
    item_id="potion", nome="Potion", categoria=CategoriaDeItem.CURA, potencia=20.0, quantidade=2
)
SUPER_POTION = ItemDaMochila(
    item_id="super-potion",
    nome="Super Potion",
    categoria=CategoriaDeItem.CURA,
    potencia=50.0,
    quantidade=2,
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


def membro(hp_atual_pct, nivel=10, soma=318):
    return PokemonNoTime(nivel=nivel, soma_stats_base=soma, hp_atual_pct=hp_atual_pct)


def hps(time):
    return [pokemon.hp_atual_pct for pokemon in time]


# --- Escolha ----------------------------------------------------------------


def test_escolhe_a_cura_de_menor_potencia_disponivel():
    time = [membro(60), membro(55)]

    escolhido = escolher_cura([SUPER_POTION, POTION], time)

    assert escolhido is not None
    assert escolhido.item_id == "potion"


def test_a_ordem_da_carga_nao_muda_a_escolha():
    time = [membro(60)]

    assert escolher_cura([POTION, SUPER_POTION], time) == escolher_cura(
        [SUPER_POTION, POTION], time
    )


def test_revive_entra_na_frente_quando_ha_nocauteado():
    time = [membro(0), membro(80)]

    escolhido = escolher_cura([POTION, REVIVE], time)

    assert escolhido is not None
    assert escolhido.item_id == "revive"


def test_revive_nao_e_escolhido_sem_nocauteado():
    time = [membro(70), membro(80)]

    escolhido = escolher_cura([REVIVE, POTION], time)

    assert escolhido is not None
    assert escolhido.item_id == "potion"


def test_so_revive_na_carga_e_ninguem_nocauteado_nao_gasta_nada():
    assert escolher_cura([REVIVE], [membro(70)]) is None


def test_carga_sem_cura_nenhuma_devolve_nada():
    # E este None que faz a contagem de derrotas avancar (regra 9).
    assert escolher_cura([POKE_BALL], [membro(40)]) is None
    assert escolher_cura([], [membro(40)]) is None


def test_linha_zerada_nao_conta_como_cura_disponivel():
    vazia = ItemDaMochila(
        item_id="potion",
        nome="Potion",
        categoria=CategoriaDeItem.CURA,
        potencia=20.0,
        quantidade=0,
    )

    assert escolher_cura([vazia], [membro(40)]) is None


def test_time_inteiro_em_100_nao_gasta_item():
    assert escolher_cura([POTION], [membro(100), membro(100)]) is None


def test_escolha_e_deterministica():
    time = [membro(0), membro(50)]
    carga = [SUPER_POTION, REVIVE, POTION]

    assert escolher_cura(carga, time) == escolher_cura(carga, time)


# --- Efeito -----------------------------------------------------------------


def test_cura_soma_a_potencia_ao_time_todo():
    time = [membro(60), membro(55), membro(30)]

    assert hps(aplicar_cura(POTION, time)) == [80, 75, 50]


def test_cura_nao_passa_de_100():
    time = [membro(95), membro(100), membro(81)]

    assert hps(aplicar_cura(POTION, time)) == [100, 100, 100]
    assert all(
        pokemon.hp_atual_pct <= balance.BASE_PERCENTUAL
        for pokemon in aplicar_cura(SUPER_POTION, time)
    )


def test_revive_levanta_so_um_nocauteado_e_e_o_primeiro_do_time():
    time = [membro(40), membro(0), membro(0)]

    assert hps(aplicar_cura(REVIVE, time)) == [40, 50, 0]


def test_revive_sem_nocauteado_devolve_o_time_intacto():
    time = [membro(40), membro(90)]

    assert hps(aplicar_cura(REVIVE, time)) == [40, 90]


def test_pokebola_nao_cura_nada():
    time = [membro(40)]

    assert hps(aplicar_cura(POKE_BALL, time)) == [40]


def test_efeito_preserva_a_ordem_e_o_resto_do_estado():
    time = [membro(40, nivel=12, soma=300), membro(10, nivel=7, soma=250)]

    curado = aplicar_cura(POTION, time)

    assert [pokemon.nivel for pokemon in curado] == [12, 7]
    assert [pokemon.soma_stats_base for pokemon in curado] == [300, 250]


def test_efeito_nao_altera_o_time_recebido():
    time = [membro(40)]

    aplicar_cura(POTION, time)

    assert hps(time) == [40]


def test_item_com_potencia_fracionaria_e_recusado():
    estranho = ItemDaMochila(
        item_id="potion",
        nome="Potion",
        categoria=CategoriaDeItem.CURA,
        potencia=20.5,
        quantidade=1,
    )

    with pytest.raises(ItemInvalido):
        aplicar_cura(estranho, [membro(40)])


# --- Leitura do time --------------------------------------------------------


def test_ha_nocauteado_e_ha_o_que_curar():
    assert ha_nocauteado([membro(0), membro(50)]) is True
    assert ha_nocauteado([membro(1), membro(50)]) is False
    assert ha_o_que_curar([membro(100), membro(99)]) is True
    assert ha_o_que_curar([membro(100)]) is False
