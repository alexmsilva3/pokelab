"""Kit inicial do laboratorio (spec 002, criterio de aceite 1).

O kit e o que separa um laboratorio recem-criado de um laboratorio capaz de
despachar a primeira expedicao. Aqui se verifica o conteudo e o Artigo III.
"""

import random
from dataclasses import FrozenInstanceError

import pytest

from app.game import balance
from app.game.erros import KitInicialInvalido
from app.game.experience import experiencia_total_para_nivel
from app.game.kit_inicial import EspecieInicial, montar_kit_inicial
from app.game.trainers import NOMES_DE_TREINADOR, gerar_avatar

# As tres especies iniciais como o servico as leria do seed.
INICIAIS = (
    EspecieInicial(id=1, nome="Bulbasaur", curva_crescimento="media_lenta"),
    EspecieInicial(id=4, nome="Charmander", curva_crescimento="media_lenta"),
    EspecieInicial(id=7, nome="Squirtle", curva_crescimento="media_lenta"),
)


def montar(semente: int = 42):
    return montar_kit_inicial(INICIAIS, random.Random(semente))


def test_kit_tem_exatamente_os_tres_iniciais():
    kit = montar()
    assert len(kit.pokemon) == 3
    assert tuple(p.especie_id for p in kit.pokemon) == balance.STARTER_SPECIES_IDS


def test_iniciais_nascem_no_nivel_do_balance():
    assert all(p.nivel == balance.STARTER_LEVEL for p in montar().pokemon)


def test_iniciais_nascem_com_a_experiencia_acumulada_da_propria_curva():
    for pokemon, especie in zip(montar().pokemon, INICIAIS, strict=True):
        assert pokemon.experiencia == experiencia_total_para_nivel(
            especie.curva_crescimento, balance.STARTER_LEVEL
        )
    # media_lenta no nivel 5: 1.2*125 - 15*25 + 500 - 140
    assert montar().pokemon[0].experiencia == 135


def test_curva_diferente_rende_experiencia_diferente():
    outras = (
        EspecieInicial(id=1, nome="Bulbasaur", curva_crescimento="rapida"),
        EspecieInicial(id=4, nome="Charmander", curva_crescimento="media_rapida"),
        EspecieInicial(id=7, nome="Squirtle", curva_crescimento="lenta"),
    )
    kit = montar_kit_inicial(outras, random.Random(1))
    assert [p.experiencia for p in kit.pokemon] == [100, 125, 156]


def test_kit_traz_os_treinadores_iniciais_com_nome_e_avatar():
    kit = montar()
    assert len(kit.treinadores) == balance.TREINADORES_NO_KIT_INICIAL
    for treinador in kit.treinadores:
        assert treinador.nome in NOMES_DE_TREINADOR
        assert treinador.avatar == gerar_avatar(treinador.nome)
        assert treinador.avatar.cor.startswith("#")


def test_kit_traz_o_estoque_inicial_sem_quantidade_negativa():
    kit = montar()
    assert {item.item_id: item.quantidade for item in kit.itens} == balance.ESTOQUE_INICIAL
    assert all(item.quantidade >= 0 for item in kit.itens)


def test_kit_desbloqueia_apenas_o_local_inicial():
    assert montar().locais_desbloqueados == (balance.LOCAL_INICIAL_ID,)


def test_kit_marca_os_tres_iniciais_como_capturados_na_pokedex():
    entradas = montar().pokedex
    assert tuple(e.especie_id for e in entradas) == balance.STARTER_SPECIES_IDS
    assert all(e.visto and e.capturado for e in entradas)


def test_mesmo_seed_produz_exatamente_o_mesmo_kit():
    assert montar(2024) == montar(2024)


def test_seeds_diferentes_variam_o_treinador_em_alguma_amostra():
    nomes = {montar(semente).treinadores[0].nome for semente in range(50)}
    assert len(nomes) > 1


def test_ordem_das_especies_na_entrada_nao_muda_o_kit():
    invertidas = tuple(reversed(INICIAIS))
    assert montar_kit_inicial(invertidas, random.Random(5)) == montar_kit_inicial(
        INICIAIS, random.Random(5)
    )


def test_kit_e_imutavel():
    kit = montar()
    with pytest.raises(FrozenInstanceError):
        kit.pokemon = ()  # type: ignore[misc]


def test_especie_fora_da_lista_de_iniciais_e_recusada():
    erradas = (
        EspecieInicial(id=1, nome="Bulbasaur", curva_crescimento="media_lenta"),
        EspecieInicial(id=4, nome="Charmander", curva_crescimento="media_lenta"),
        EspecieInicial(id=25, nome="Pikachu", curva_crescimento="media_rapida"),
    )
    with pytest.raises(KitInicialInvalido, match="especies"):
        montar_kit_inicial(erradas, random.Random(0))


def test_especie_faltando_e_recusada():
    with pytest.raises(KitInicialInvalido, match="especies"):
        montar_kit_inicial(INICIAIS[:2], random.Random(0))


def test_especie_repetida_e_recusada():
    repetidas = (*INICIAIS, INICIAIS[0])
    with pytest.raises(KitInicialInvalido, match="repetidas"):
        montar_kit_inicial(repetidas, random.Random(0))


def test_lista_vazia_e_recusada():
    with pytest.raises(KitInicialInvalido, match="nenhuma"):
        montar_kit_inicial((), random.Random(0))
