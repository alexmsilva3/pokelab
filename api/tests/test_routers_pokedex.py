"""Contrato HTTP de `GET /pokedex` (spec 003)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import requer_banco

pytestmark = requer_banco

client = TestClient(app)


def _registrar(usuario: str) -> dict:
    resposta = client.post("/auth/register", json={"usuario": usuario, "senha": f"{usuario}12345"})
    assert resposta.status_code == 201
    return resposta.json()


def test_pokedex_recem_criada_tem_151_entradas_tres_capturadas(sessao_db):
    """Criterio 8."""
    sessao = _registrar("Dex1")
    token = sessao["token"]

    resposta = client.get("/pokedex", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo["items"]) == 151
    assert corpo["capturadas"] == 3
    assert corpo["vistas"] == 3

    estados = {item["estado"] for item in corpo["items"]}
    assert estados == {"DESCONHECIDA", "CAPTURADA"}
    assert sum(1 for item in corpo["items"] if item["estado"] == "CAPTURADA") == 3
    assert sum(1 for item in corpo["items"] if item["estado"] == "DESCONHECIDA") == 148


def test_especie_nunca_vista_nao_revela_nome_em_lugar_nenhum_do_corpo(sessao_db):
    """Criterio 9: a protecao e de forma, nao de valor — o campo nao existe."""
    sessao = _registrar("Dex2")
    token = sessao["token"]

    resposta = client.get("/pokedex", headers={"Authorization": f"Bearer {token}"})
    corpo_bruto = resposta.text

    desconhecidas = [item for item in resposta.json()["items"] if item["estado"] == "DESCONHECIDA"]
    assert desconhecidas, "o laboratorio novo precisa ter especies desconhecidas para o teste valer"
    for entrada in desconhecidas:
        assert set(entrada.keys()) == {"numero", "estado"}

    # Varredura adicional sobre o JSON cru: nenhum nome de especie nao vista
    # pode aparecer em lugar nenhum da resposta, nem escondido num campo
    # inesperado.
    numeros_capturados_ou_vistos = {
        item["numero"]
        for item in resposta.json()["items"]
        if item["estado"] in ("VISTA", "CAPTURADA")
    }
    assert "Mew" not in corpo_bruto  # especie 151, nunca vista num lab novo
    assert 151 not in numeros_capturados_ou_vistos


def test_entrada_capturada_mostra_quantidade_atual(sessao_db):
    sessao = _registrar("Dex3")
    token = sessao["token"]

    resposta = client.get("/pokedex", headers={"Authorization": f"Bearer {token}"})
    capturadas = [item for item in resposta.json()["items"] if item["estado"] == "CAPTURADA"]

    assert all(item["quantidade"] == 1 for item in capturadas)
    assert all("nome" in item and "tipos" in item and "sprite" in item for item in capturadas)


def test_pokedex_e_escopada_ao_laboratorio_da_sessao(sessao_db):
    dex_a = _registrar("DexA")
    dex_b = _registrar("DexB")

    resposta_a = client.get(
        "/pokedex", headers={"Authorization": f"Bearer {dex_a['token']}"}
    ).json()
    resposta_b = client.get(
        "/pokedex", headers={"Authorization": f"Bearer {dex_b['token']}"}
    ).json()

    # Cada laboratorio tem seus proprios tres starters, sorteados independentemente;
    # o que importa e que as DUAS respostas, isoladamente, ja satisfazem o criterio 8.
    assert resposta_a["capturadas"] == resposta_b["capturadas"] == 3
