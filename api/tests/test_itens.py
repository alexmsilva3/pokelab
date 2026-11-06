"""Criterio de aceite 11 da spec 003: a mochila do laboratorio."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.game import balance
from app.main import app
from app.models import ItemEstoque
from tests.conftest import requer_banco

pytestmark = requer_banco

client = TestClient(app)


def _registrar(usuario: str) -> dict:
    resposta = client.post("/auth/register", json={"usuario": usuario, "senha": f"{usuario}12345"})
    assert resposta.status_code == 201
    return resposta.json()


def _cabecalho(sessao: dict) -> dict:
    return {"Authorization": f"Bearer {sessao['token']}"}


# --- Criterio 11 ---------------------------------------------------------------


def test_mochila_de_laboratorio_recem_criado_mostra_os_itens_do_kit_e_nenhum_zerado(sessao_db):
    sessao = _registrar("Crit11_Mochila")

    resposta = client.get("/items", headers=_cabecalho(sessao))

    assert resposta.status_code == 200
    corpo = resposta.json()
    ids_recebidos = {item["item_id"] for item in corpo["items"]}
    assert ids_recebidos == set(balance.ESTOQUE_INICIAL)
    for item in corpo["items"]:
        assert item["quantidade"] == balance.ESTOQUE_INICIAL[item["item_id"]]
        assert item["quantidade"] > 0


def test_item_com_quantidade_zero_nao_aparece_na_mochila(sessao_db):
    sessao = _registrar("Crit11_Zerado")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])

    estoque_zerado = sessao_db.get(ItemEstoque, (laboratorio_id, "revive"))
    estoque_zerado.quantidade = 0
    sessao_db.commit()

    resposta = client.get("/items", headers=_cabecalho(sessao))

    ids_recebidos = {item["item_id"] for item in resposta.json()["items"]}
    assert "revive" not in ids_recebidos
    # Os demais itens do kit, que nao foram zerados, continuam aparecendo.
    assert ids_recebidos == set(balance.ESTOQUE_INICIAL) - {"revive"}


# --- Escopo ----------------------------------------------------------------


def test_mochila_e_escopada_ao_laboratorio_da_sessao(sessao_db):
    sessao_a = _registrar("Crit11Escopo_A")
    sessao_b = _registrar("Crit11Escopo_B")
    laboratorio_a = uuid.UUID(sessao_a["laboratorio"]["id"])

    estoque_de_a = sessao_db.get(ItemEstoque, (laboratorio_a, "poke-ball"))
    estoque_de_a.quantidade = 0
    sessao_db.commit()

    mochila_a = client.get("/items", headers=_cabecalho(sessao_a)).json()
    mochila_b = client.get("/items", headers=_cabecalho(sessao_b)).json()

    ids_a = {item["item_id"] for item in mochila_a["items"]}
    ids_b = {item["item_id"] for item in mochila_b["items"]}
    assert "poke-ball" not in ids_a
    assert "poke-ball" in ids_b


def test_sem_token_devolve_401(sessao_db):
    assert client.get("/items").status_code == 401
