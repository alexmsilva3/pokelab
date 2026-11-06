"""Contrato HTTP de `GET /map` e `GET /map/{id}` (spec 005).

Os doze testes principais seguem a numeracao dos criterios de aceite do
`spec.md`. Depois deles vem a cobertura extra que a constituicao exige para
qualquer rota autenticada e qualquer leitura escopada por laboratorio: o
vazamento do pool de encontros, a ausencia de qualquer contagem reveladora, a
expansao do alcance passo a passo, a promessa de que desbloquear encurta a
viagem, escopo entre laboratorios, o avistamento de uma especie, o 404 sem
500, a coerencia entre `/map` e `/map/{id}`, e o numero constante de
consultas.

Cada teste cobre o comportamento observavel pela API (Artigo IX), nunca a
forma interna de `services/mapa.py` ou `repositories/mapa.py`. Onde a spec
exige um estado que nenhuma rota desta fase produz — um local desbloqueado
fora de ordem, uma especie avistada —, o teste forja esse estado direto no
banco, como o resto da suite ja faz (`test_trainers.py`, `test_pokemon.py`).
"""

from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.core.database import engine
from app.game.mapa import LocalNoGrafo, duracao_estimada, montar_grafo, rotas_otimas
from app.main import app
from app.models import Local, LocalDesbloqueado, PokedexAvistamento
from tests.conftest import requer_banco

pytestmark = requer_banco

client = TestClient(app)

RAIZ = Path(__file__).resolve().parent.parent.parent
DIR_SEED = RAIZ / "data" / "seed"

# Os dez locais da v1 (plan.md da spec 005), usados pelos testes que montam o
# caminho inteiro ate um local fora de alcance.
CAMINHO_ATE_ROUTE_3 = (
    "route-1",
    "viridian-city",
    "route-2",
    "viridian-forest",
    "pewter-city",
    "route-3",
)

CAMPOS_DO_LOCAL_DETALHADO = {
    "id",
    "nome",
    "tipo",
    "nivel_dificuldade",
    "nivel_selvagem_min",
    "nivel_selvagem_max",
    "estado",
    "origem_id",
    "origem_nome",
    "duracao_estimada_minutos",
    "proximo_passo_id",
    "proximo_passo_nome",
    "encontros_base",
    "especies_avistadas",
}


# --- Apoio -------------------------------------------------------------------


def _registrar(usuario: str) -> dict:
    resposta = client.post("/auth/register", json={"usuario": usuario, "senha": f"{usuario}12345"})
    assert resposta.status_code == 201
    return resposta.json()


def _cabecalho(sessao: dict) -> dict:
    return {"Authorization": f"Bearer {sessao['token']}"}


def _laboratorio_id(sessao: dict) -> uuid.UUID:
    return uuid.UUID(sessao["laboratorio"]["id"])


def _mapa(sessao: dict) -> dict:
    resposta = client.get("/map", headers=_cabecalho(sessao))
    assert resposta.status_code == 200
    return resposta.json()


def _resposta_local(sessao: dict, local_id: str, treinador_id: str | None = None):
    params = {"treinador_id": treinador_id} if treinador_id else {}
    return client.get(f"/map/{local_id}", params=params, headers=_cabecalho(sessao))


def _local(sessao: dict, local_id: str, treinador_id: str | None = None) -> dict:
    resposta = _resposta_local(sessao, local_id, treinador_id)
    assert resposta.status_code == 200
    return resposta.json()


def _item_do_mapa(mapa: dict, local_id: str) -> dict:
    return next(item for item in mapa["items"] if item["id"] == local_id)


def _treinador_id(sessao: dict) -> str:
    resposta = client.get("/trainers", headers=_cabecalho(sessao))
    assert resposta.status_code == 200
    return resposta.json()["items"][0]["id"]


def _desbloquear(sessao_db, laboratorio_id: uuid.UUID, *local_ids: str) -> None:
    for local_id in local_ids:
        sessao_db.add(LocalDesbloqueado(laboratorio_id=laboratorio_id, local_id=local_id))
    sessao_db.commit()


def _avistar(sessao_db, laboratorio_id: uuid.UUID, local_id: str, especie_id: int) -> None:
    sessao_db.add(
        PokedexAvistamento(
            laboratorio_id=laboratorio_id, especie_id=especie_id, local_id=local_id, vezes_visto=1
        )
    )
    sessao_db.commit()


@contextmanager
def _contar_consultas():
    contagem = {"total": 0}

    def _ouvir(conn, cursor, statement, parameters, context, executemany):
        contagem["total"] += 1

    event.listen(engine, "before_cursor_execute", _ouvir)
    try:
        yield contagem
    finally:
        event.remove(engine, "before_cursor_execute", _ouvir)


# --- Criterio 1 ----------------------------------------------------------------


def test_laboratorio_recem_criado_mostra_dez_locais_pallet_visitada_route_1_alcancavel(sessao_db):
    mapa = _mapa(_registrar("MapaCriterio1"))

    assert mapa["total"] == 10
    assert len(mapa["items"]) == 10
    assert mapa["visitados"] == 1

    pallet = _item_do_mapa(mapa, "pallet-town")
    assert pallet["estado"] == "VISITADO"

    route_1 = _item_do_mapa(mapa, "route-1")
    assert route_1["estado"] == "ALCANCAVEL"


# --- Criterio 2 ----------------------------------------------------------------


def test_cerulean_city_esta_fora_de_alcance_num_laboratorio_novo(sessao_db):
    sessao = _registrar("MapaCriterio2")

    corpo = _local(sessao, "cerulean-city")

    assert corpo["estado"] == "FORA_DE_ALCANCE"
    assert corpo["origem_id"] is None
    assert corpo["duracao_estimada_minutos"] is None


# --- Criterio 3 ----------------------------------------------------------------


def test_pewter_city_informa_que_e_preciso_visitar_route_1_antes(sessao_db):
    sessao = _registrar("MapaCriterio3")

    corpo = _local(sessao, "pewter-city")

    assert corpo["estado"] == "FORA_DE_ALCANCE"
    assert corpo["proximo_passo_id"] == "route-1"
    assert corpo["proximo_passo_nome"] == "Route 1"


# --- Criterio 4 ----------------------------------------------------------------


def test_local_alcancavel_mostra_de_onde_a_ida_partiria_e_quanto_tempo_leva(sessao_db):
    sessao = _registrar("MapaCriterio4")

    corpo = _local(sessao, "route-1")

    assert corpo["estado"] == "ALCANCAVEL"
    assert corpo["origem_id"] == "pallet-town"
    assert corpo["origem_nome"] == "Pallet Town"
    assert isinstance(corpo["duracao_estimada_minutos"], int)
    assert corpo["duracao_estimada_minutos"] > 0


# --- Criterio 5 ----------------------------------------------------------------


def test_route_1_visitada_torna_viridian_city_alcancavel(sessao_db):
    sessao = _registrar("MapaCriterio5")
    laboratorio_id = _laboratorio_id(sessao)

    assert _item_do_mapa(_mapa(sessao), "viridian-city")["estado"] == "FORA_DE_ALCANCE"

    _desbloquear(sessao_db, laboratorio_id, "route-1")

    assert _item_do_mapa(_mapa(sessao), "viridian-city")["estado"] == "ALCANCAVEL"


# --- Criterio 6 ----------------------------------------------------------------


def test_route_1_visitada_continua_sendo_destino_valido(sessao_db):
    sessao = _registrar("MapaCriterio6")
    laboratorio_id = _laboratorio_id(sessao)

    _desbloquear(sessao_db, laboratorio_id, "route-1")

    corpo = _local(sessao, "route-1")
    assert corpo["estado"] == "VISITADO"


# --- Criterio 7 (e item extra "desbloqueio encurta a viagem") ------------------


def test_route_3_desbloqueada_encurta_a_ida_a_mt_moon_mesmo_partindo_so_de_pallet(sessao_db):
    """Criterio 7: a ida ate um local depende de onde a viagem parte, e a
    origem mostrada e sempre a mais rapida disponivel.

    Mt. Moon esta fora de alcance partindo so de Pallet Town, e o professor
    nunca chega a ver a duracao dessa viagem longa (regra 8: um local fora de
    alcance nao mostra tempo nenhum). O que ele ve, assim que Route 3 abre
    Mt. Moon, e a duracao mais curta ja calculada a partir dali — e essa
    duracao e sempre menor do que a viagem que teria partido so de Pallet,
    que esta suite calcula pelo proprio dominio (SDD 4.4) com os numeros reais
    do seed, nunca por um literal copiado a mao (Artigo IV).
    """
    sessao = _registrar("MapaCriterio7")
    laboratorio_id = _laboratorio_id(sessao)

    antes = _local(sessao, "mt-moon")
    assert antes["estado"] == "FORA_DE_ALCANCE"
    assert antes["duracao_estimada_minutos"] is None

    _desbloquear(sessao_db, laboratorio_id, *CAMINHO_ATE_ROUTE_3)

    depois = _local(sessao, "mt-moon")
    assert depois["estado"] == "ALCANCAVEL"
    assert depois["origem_id"] == "route-3"
    duracao_mostrada = depois["duracao_estimada_minutos"]
    assert duracao_mostrada is not None

    locais_por_id = {local.id: local for local in sessao_db.scalars(select(Local))}
    grafo = montar_grafo(
        LocalNoGrafo(
            id=local.id,
            custo_travessia_minutos=local.custo_travessia_minutos,
            encontros_base=local.encontros_base,
            vizinhos=tuple(local.vizinhos),
        )
        for local in locais_por_id.values()
    )
    rota_desde_pallet = rotas_otimas(grafo, ("pallet-town",))["mt-moon"]
    duracao_desde_pallet = duracao_estimada(
        custo_viagem_minutos=rota_desde_pallet.custo_viagem_minutos,
        encontros_base=locais_por_id["mt-moon"].encontros_base,
    )

    assert duracao_mostrada < duracao_desde_pallet


# --- Criterio 8 (e item extra "nenhuma contagem reveladora") -------------------


def test_local_nunca_visitado_nao_revela_especie_nem_quantidade(sessao_db):
    sessao = _registrar("MapaCriterio8")

    corpo = _local(sessao, "mt-moon")

    assert corpo["especies_avistadas"] == []
    # Confere campo por campo: nenhum "total_especies" ou "progresso"
    # escondido revelaria por outro nome quantas especies existem ali.
    assert set(corpo.keys()) == CAMPOS_DO_LOCAL_DETALHADO
    assert corpo["encontros_base"] >= 1  # permitido: quantos encontros, nao quais


# --- Criterio 9 (e item extra "avistamento") -----------------------------------


def test_especie_avistada_aparece_e_as_demais_do_local_nao(sessao_db):
    sessao = _registrar("MapaCriterio9")
    laboratorio_id = _laboratorio_id(sessao)

    _avistar(sessao_db, laboratorio_id, "mt-moon", 41)  # Zubat

    corpo = _local(sessao, "mt-moon")

    nomes = {avistamento["nome"] for avistamento in corpo["especies_avistadas"]}
    assert nomes == {"Zubat"}
    assert "Geodude" not in nomes
    assert "Paras" not in nomes


def test_avistamento_nao_aparece_em_outro_local(sessao_db):
    sessao = _registrar("MapaCriterio9b")
    laboratorio_id = _laboratorio_id(sessao)

    _avistar(sessao_db, laboratorio_id, "mt-moon", 41)  # Zubat visto em Mt. Moon

    corpo_de_outro_local = _local(sessao, "cerulean-city")

    assert corpo_de_outro_local["especies_avistadas"] == []


# --- Criterio 10 ----------------------------------------------------------------


def test_local_inexistente_devolve_404_com_o_envelope_padrao(sessao_db):
    sessao = _registrar("MapaCriterio10")

    resposta = _resposta_local(sessao, "saffron-city")

    assert resposta.status_code == 404
    corpo = resposta.json()
    assert corpo["erro"]["codigo"] == "LOCAL_DESCONHECIDO"


# --- Criterio 11 ----------------------------------------------------------------


def test_dois_professores_com_progressos_diferentes_veem_mapas_diferentes(sessao_db):
    sessao_a = _registrar("MapaCriterio11A")
    sessao_b = _registrar("MapaCriterio11B")

    _desbloquear(sessao_db, _laboratorio_id(sessao_a), "route-1", "viridian-city")

    mapa_a = _mapa(sessao_a)
    mapa_b = _mapa(sessao_b)

    assert mapa_a["visitados"] == 3
    assert mapa_b["visitados"] == 1
    assert _item_do_mapa(mapa_a, "viridian-city")["estado"] == "VISITADO"
    assert _item_do_mapa(mapa_b, "viridian-city")["estado"] == "FORA_DE_ALCANCE"


# --- Criterio 12 (e item extra "vazamento do pool de encontros") ---------------


def test_pool_de_encontros_do_seed_nunca_aparece_na_resposta(sessao_db):
    """Criterio 12, e o teste mais importante da fase: varre o corpo inteiro
    de `GET /map` e de `GET /map/{id}` atras do nome de cada especie que o
    seed associa a um local nunca visitado. Os nomes vem do proprio seed, para
    o teste continuar valendo quando o pool mudar (Artigo V)."""
    sessao = _registrar("MapaCriterio12")

    encontros = json.loads((DIR_SEED / "encounters.json").read_text(encoding="utf-8"))
    especies = {
        especie["id"]: especie["nome"]
        for especie in json.loads((DIR_SEED / "species.json").read_text(encoding="utf-8"))
    }
    nomes_do_pool_de_mt_moon = {
        especies[encontro["especie_id"]] for encontro in encontros["mt-moon"]
    }
    assert nomes_do_pool_de_mt_moon, "o seed precisa povoar mt-moon para o teste valer"

    corpo_do_mapa = client.get("/map", headers=_cabecalho(sessao)).text
    corpo_do_local = _resposta_local(sessao, "mt-moon").text

    for nome_da_especie in nomes_do_pool_de_mt_moon:
        assert nome_da_especie not in corpo_do_mapa
        assert nome_da_especie not in corpo_do_local


# --- Itens extras exigidos pela constituicao -----------------------------------


def test_desbloqueio_expande_o_alcance_passo_a_passo_de_pallet_ate_cerulean(sessao_db):
    """O conjunto ALCANCAVEL cresce conforme cada local do caminho e
    desbloqueado, um passo de cada vez, ate Cerulean City."""
    sessao = _registrar("MapaExpansao")
    laboratorio_id = _laboratorio_id(sessao)

    caminho_completo = (*CAMINHO_ATE_ROUTE_3, "mt-moon", "cerulean-city")
    ainda_fora_de_alcance = set(caminho_completo)

    for proximo_local in caminho_completo:
        estado_antes = _item_do_mapa(_mapa(sessao), proximo_local)["estado"]
        mensagem = f"{proximo_local} deveria estar alcancavel antes de ser desbloqueado"
        assert estado_antes == "ALCANCAVEL", mensagem

        _desbloquear(sessao_db, laboratorio_id, proximo_local)
        ainda_fora_de_alcance.discard(proximo_local)

        mapa = _mapa(sessao)
        assert _item_do_mapa(mapa, proximo_local)["estado"] == "VISITADO"
        for local_id in ainda_fora_de_alcance:
            estado = _item_do_mapa(mapa, local_id)["estado"]
            assert estado in ("ALCANCAVEL", "FORA_DE_ALCANCE")


def test_treinador_de_outro_laboratorio_em_map_id_devolve_404(sessao_db):
    sessao_a = _registrar("MapaEscopoA")
    sessao_b = _registrar("MapaEscopoB")

    treinador_de_b = _treinador_id(sessao_b)

    resposta = _resposta_local(sessao_a, "route-1", treinador_id=treinador_de_b)

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"


def test_treinador_do_proprio_laboratorio_e_aceito_em_map_id(sessao_db):
    sessao = _registrar("MapaTreinadorProprio")

    treinador_id = _treinador_id(sessao)

    resposta = _resposta_local(sessao, "route-1", treinador_id=treinador_id)

    assert resposta.status_code == 200


def test_estado_do_local_e_o_mesmo_em_map_e_em_map_id(sessao_db):
    """Se `GET /map` e `GET /map/{id}` divergissem sobre o estado de um
    local, haveria duas fontes de verdade — o que o plan.md da spec 005
    proibe explicitamente."""
    sessao = _registrar("MapaCoerencia")
    laboratorio_id = _laboratorio_id(sessao)
    _desbloquear(sessao_db, laboratorio_id, "route-1")

    mapa = _mapa(sessao)

    for item_da_lista in mapa["items"]:
        detalhe = _local(sessao, item_da_lista["id"])
        assert detalhe["estado"] == item_da_lista["estado"]
        assert detalhe["origem_id"] == item_da_lista["origem_id"]
        assert detalhe["duracao_estimada_minutos"] == item_da_lista["duracao_estimada_minutos"]
        assert detalhe["proximo_passo_id"] == item_da_lista["proximo_passo_id"]


def test_get_map_emite_um_numero_constante_de_consultas(sessao_db):
    """N+1: a tela do mapa resolve os dez locais com um numero fixo de
    consultas, qualquer que seja o progresso do laboratorio — nunca uma
    consulta por local."""
    sessao_pouco_progresso = _registrar("MapaConsultasA")
    sessao_muito_progresso = _registrar("MapaConsultasB")
    _desbloquear(
        sessao_db,
        _laboratorio_id(sessao_muito_progresso),
        *CAMINHO_ATE_ROUTE_3,
        "mt-moon",
        "cerulean-city",
    )

    with _contar_consultas() as contagem_pouco:
        resposta = client.get("/map", headers=_cabecalho(sessao_pouco_progresso))
        assert resposta.status_code == 200

    with _contar_consultas() as contagem_muito:
        resposta = client.get("/map", headers=_cabecalho(sessao_muito_progresso))
        assert resposta.status_code == 200

    assert contagem_pouco["total"] == contagem_muito["total"]
    assert contagem_pouco["total"] <= 5
