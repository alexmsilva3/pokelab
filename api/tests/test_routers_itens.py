"""Contrato HTTP de `GET /items` (spec 003)."""

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


def test_mochila_recem_criada_mostra_o_kit_sem_item_zerado(sessao_db):
    """Criterio 11."""
    sessao = _registrar("Itens1")

    resposta = client.get("/items", headers={"Authorization": f"Bearer {sessao['token']}"})

    assert resposta.status_code == 200
    corpo = resposta.json()
    ids_recebidos = {item["item_id"] for item in corpo["items"]}
    assert ids_recebidos == set(balance.ESTOQUE_INICIAL)
    for item in corpo["items"]:
        assert item["quantidade"] == balance.ESTOQUE_INICIAL[item["item_id"]]
        assert item["quantidade"] > 0


def test_item_com_quantidade_zero_nao_aparece(sessao_db):
    sessao = _registrar("Itens2")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])

    zerado = sessao_db.get(ItemEstoque, (laboratorio_id, "revive"))
    zerado.quantidade = 0
    sessao_db.commit()

    resposta = client.get("/items", headers={"Authorization": f"Bearer {sessao['token']}"})

    ids_recebidos = {item["item_id"] for item in resposta.json()["items"]}
    assert "revive" not in ids_recebidos


def test_sem_token_devolve_401(sessao_db):
    assert client.get("/items").status_code == 401
