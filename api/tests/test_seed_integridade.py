"""Integridade do acervo em data/seed/.

Verifica os criterios de aceite da spec 001 sobre os arquivos, sem precisar de
banco. A carga no Postgres e coberta por tests/test_seed_carga.py.
"""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parent.parent.parent
DIR_SEED = RAIZ / "data" / "seed"
DIR_SPRITES = RAIZ / "data" / "sprites"

TOTAL_ESPECIES = 151
TOTAL_LOCAIS = 10
LOCAL_INICIAL = "pallet-town"

CURVAS_VALIDAS = {"rapida", "media_rapida", "media_lenta", "lenta"}
TIPOS_DE_LOCAL = {"CIDADE", "ROTA", "MASMORRA"}
CATEGORIAS_DE_ITEM = {"POKEBOLA", "CURA", "REVIVE"}


def _ler(nome: str) -> Any:
    return json.loads((DIR_SEED / nome).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def especies() -> list[dict[str, Any]]:
    return _ler("species.json")


@pytest.fixture(scope="module")
def locais() -> list[dict[str, Any]]:
    return _ler("locations.json")


@pytest.fixture(scope="module")
def encontros() -> dict[str, list[dict[str, Any]]]:
    return _ler("encounters.json")


@pytest.fixture(scope="module")
def itens() -> list[dict[str, Any]]:
    return _ler("items.json")


# --- Especies --------------------------------------------------------------


def test_sao_exatamente_151_especies_sem_lacuna(especies):
    ids = sorted(e["id"] for e in especies)
    assert ids == list(range(1, TOTAL_ESPECIES + 1))


def test_nenhum_campo_obrigatorio_vazio(especies):
    obrigatorios = (
        "nome",
        "tipo_primario",
        "hp_base",
        "ataque_base",
        "defesa_base",
        "ataque_especial_base",
        "defesa_especial_base",
        "velocidade_base",
        "experiencia_base",
        "taxa_captura",
        "curva_crescimento",
        "sprite_frente",
        "sprite_costas",
    )
    vazios = [
        f"{e['id']}.{campo}"
        for e in especies
        for campo in obrigatorios
        if e.get(campo) in (None, "")
    ]
    assert not vazios


def test_curvas_de_crescimento_sao_conhecidas(especies):
    assert {e["curva_crescimento"] for e in especies} <= CURVAS_VALIDAS


def test_toda_evolucao_aponta_para_especie_existente(especies):
    ids = {e["id"] for e in especies}
    orfas = [
        (e["id"], e["evolui_para_id"])
        for e in especies
        if e["evolui_para_id"] is not None and e["evolui_para_id"] not in ids
    ]
    assert not orfas


def test_toda_evolucao_tem_nivel(especies):
    sem_nivel = [e["id"] for e in especies if e["evolui_para_id"] and not e["evolui_em_nivel"]]
    assert not sem_nivel


def test_os_tres_iniciais_estao_marcados(especies):
    assert sorted(e["id"] for e in especies if e["e_inicial"]) == [1, 4, 7]


def test_charmander_evolui_para_charmeleon_no_nivel_16(especies):
    charmander = next(e for e in especies if e["id"] == 4)
    assert charmander["evolui_para_id"] == 5
    assert charmander["evolui_em_nivel"] == 16


def test_taxa_de_captura_esta_na_faixa_valida(especies):
    fora = [e["id"] for e in especies if not 0 < e["taxa_captura"] <= 255]
    assert not fora


def test_todo_sprite_referenciado_existe_no_disco(especies):
    ausentes = [
        arquivo
        for e in especies
        for arquivo in (e["sprite_frente"], e["sprite_costas"])
        if not (DIR_SPRITES / arquivo).is_file()
    ]
    assert not ausentes


# --- Locais ----------------------------------------------------------------


def test_sao_dez_locais_com_ids_unicos(locais):
    ids = [local["id"] for local in locais]
    assert len(ids) == TOTAL_LOCAIS
    assert len(set(ids)) == TOTAL_LOCAIS


def test_apenas_pallet_town_comeca_desbloqueada(locais):
    iniciais = [local["id"] for local in locais if local["e_inicial"]]
    assert iniciais == [LOCAL_INICIAL]


def test_tipos_de_local_sao_conhecidos(locais):
    assert {local["tipo"] for local in locais} <= TIPOS_DE_LOCAL


def test_todo_local_declara_custo_de_travessia_e_encontros(locais):
    incompletos = [
        local["id"]
        for local in locais
        if local.get("custo_travessia_minutos", 0) <= 0 or local.get("encontros_base", 0) <= 0
    ]
    assert not incompletos


def test_custo_de_travessia_segue_o_tipo_do_local(locais):
    # Cidade e passagem facil, masmorra e cara. A regra existe para que o mapa
    # cresca sem que cada local novo invente seu proprio custo.
    esperado = {"CIDADE": 3, "ROTA": 4, "MASMORRA": 8}
    divergentes = [
        local["id"]
        for local in locais
        if local["custo_travessia_minutos"] != esperado[local["tipo"]]
    ]
    assert not divergentes


def test_duracao_base_nao_existe_mais(locais):
    # A duracao e calculada pelo caminho (SDD 4.3), nao declarada por local.
    residuos = [local["id"] for local in locais if "duracao_base_minutos" in local]
    assert not residuos


def test_faixa_de_nivel_selvagem_e_coerente(locais):
    invertidas = [
        local["id"] for local in locais if local["nivel_selvagem_min"] > local["nivel_selvagem_max"]
    ]
    assert not invertidas


def test_vizinhanca_e_reciproca(locais):
    mapa = {local["id"]: set(local["vizinhos"]) for local in locais}
    assimetricas = [
        (origem, destino)
        for origem, vizinhos in mapa.items()
        for destino in vizinhos
        if origem not in mapa.get(destino, set())
    ]
    assert not assimetricas


def test_toda_vizinhanca_aponta_para_local_existente(locais):
    ids = {local["id"] for local in locais}
    orfas = [
        (local["id"], vizinho)
        for local in locais
        for vizinho in local["vizinhos"]
        if vizinho not in ids
    ]
    assert not orfas


def test_todo_local_e_alcancavel_a_partir_de_pallet_town(locais):
    mapa = {local["id"]: local["vizinhos"] for local in locais}
    visitados = {LOCAL_INICIAL}
    fila = deque([LOCAL_INICIAL])
    while fila:
        atual = fila.popleft()
        for vizinho in mapa[atual]:
            if vizinho not in visitados:
                visitados.add(vizinho)
                fila.append(vizinho)
    assert visitados == set(mapa)


# --- Encontros -------------------------------------------------------------


def test_todo_local_tem_pool_de_encontros_nao_vazio(locais, encontros):
    vazios = [local["id"] for local in locais if not encontros.get(local["id"])]
    assert not vazios


def test_nenhum_pool_referencia_local_inexistente(locais, encontros):
    ids = {local["id"] for local in locais}
    assert set(encontros) <= ids


def test_toda_especie_de_encontro_existe(especies, encontros):
    ids = {e["id"] for e in especies}
    orfas = [
        (local_id, entrada["especie_id"])
        for local_id, pool in encontros.items()
        for entrada in pool
        if entrada["especie_id"] not in ids
    ]
    assert not orfas


def test_pesos_de_encontro_sao_positivos(encontros):
    invalidos = [
        (local_id, entrada["especie_id"])
        for local_id, pool in encontros.items()
        for entrada in pool
        if entrada["peso"] <= 0
    ]
    assert not invalidos


def test_nivel_de_encontro_respeita_a_faixa_do_local(locais, encontros):
    faixas = {
        local["id"]: (local["nivel_selvagem_min"], local["nivel_selvagem_max"]) for local in locais
    }
    fora = [
        (local_id, entrada["especie_id"])
        for local_id, pool in encontros.items()
        for entrada in pool
        if not (
            faixas[local_id][0]
            <= entrada["nivel_min"]
            <= entrada["nivel_max"]
            <= faixas[local_id][1]
        )
    ]
    assert not fora


def test_pesos_de_cada_local_somam_cem(encontros):
    # Convencao do projeto: com soma 100, o peso le-se direto como porcentagem.
    fora = {
        local_id: sum(entrada["peso"] for entrada in pool)
        for local_id, pool in encontros.items()
        if sum(entrada["peso"] for entrada in pool) != 100
    }
    assert not fora


def test_tabela_legivel_esta_em_sincronia_com_o_seed():
    # docs/encontros.md e gerado de data/seed/. Se divergir, alguem editou um dos
    # dois a mao e a documentacao passou a mentir.
    import sys

    sys.path.insert(0, str(RAIZ / "tools"))
    from tabela_encontros import montar

    destino = RAIZ / "docs" / "encontros.md"
    assert destino.is_file(), "rode tools/tabela_encontros.py"
    assert destino.read_text(encoding="utf-8") == montar(), (
        "docs/encontros.md desatualizado: rode tools/tabela_encontros.py"
    )


def test_minutos_por_encontro_do_script_espelha_o_balance():
    import sys

    sys.path.insert(0, str(RAIZ / "tools"))
    import tabela_encontros

    from app.game import balance

    assert tabela_encontros.MINUTOS_POR_ENCONTRO == balance.MINUTOS_POR_ENCONTRO


def test_nenhuma_especie_repetida_no_mesmo_pool(encontros):
    repetidas = [
        local_id
        for local_id, pool in encontros.items()
        if len({entrada["especie_id"] for entrada in pool}) != len(pool)
    ]
    assert not repetidas


# --- Itens -----------------------------------------------------------------


def test_itens_cobrem_as_tres_categorias(itens):
    assert {item["categoria"] for item in itens} == CATEGORIAS_DE_ITEM


def test_ids_de_item_sao_unicos(itens):
    ids = [item["id"] for item in itens]
    assert len(ids) == len(set(ids))


def test_toda_pokebola_do_balance_existe_no_seed(itens):
    from app.game.balance import MULTIPLICADOR_BOLA

    ids = {item["id"] for item in itens}
    assert set(MULTIPLICADOR_BOLA) <= ids


def test_a_potencia_da_pokebola_no_seed_bate_com_o_balance(itens):
    # A resolucao da expedicao usa `Item.potencia` do seed como multiplicador
    # de captura, e nao o dicionario de balance.py. Este teste e o que impede
    # as duas fontes de divergirem: um ingestor que mudasse a potencia de uma
    # Pokebola moveria a economia do jogo sem ninguem decidir isso.
    from app.game.balance import MULTIPLICADOR_BOLA

    potencias = {item["id"]: item["potencia"] for item in itens}
    assert {item_id: potencias[item_id] for item_id in MULTIPLICADOR_BOLA} == MULTIPLICADOR_BOLA


def test_todo_item_do_estoque_inicial_existe_no_seed(itens):
    from app.game.balance import ESTOQUE_INICIAL

    ids = {item["id"] for item in itens}
    assert set(ESTOQUE_INICIAL) <= ids


def test_especies_iniciais_do_balance_existem(especies):
    from app.game.balance import STARTER_SPECIES_IDS

    ids = {e["id"] for e in especies}
    assert set(STARTER_SPECIES_IDS) <= ids


def test_local_inicial_do_balance_existe(locais):
    from app.game.balance import LOCAL_INICIAL_ID

    assert LOCAL_INICIAL_ID in {local["id"] for local in locais}
