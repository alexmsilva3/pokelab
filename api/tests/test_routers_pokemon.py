"""Contrato HTTP de `/pokemon` (spec 003): listagem, ficha e apelido."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.game import balance
from app.main import app
from app.models import PokemonInstancia
from tests.conftest import requer_banco

pytestmark = requer_banco

client = TestClient(app)


def _registrar(usuario: str) -> dict:
    resposta = client.post("/auth/register", json={"usuario": usuario, "senha": f"{usuario}12345"})
    assert resposta.status_code == 201
    return resposta.json()


def _cabecalho(sessao: dict) -> dict:
    return {"Authorization": f"Bearer {sessao['token']}"}


def test_laboratorio_recem_criado_mostra_os_tres_iniciais(sessao_db):
    """Criterio 1: imagem, nome, tipo e nivel dos tres starters."""
    sessao = _registrar("Ash")

    resposta = client.get("/pokemon", headers=_cabecalho(sessao))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 3
    assert len(corpo["items"]) == 3
    for item in corpo["items"]:
        assert item["nome"]
        assert item["sprite"]
        assert item["tipo_primario"]
        assert item["nivel"] == balance.STARTER_LEVEL


def test_paginacao_avanca_sem_mudar_o_total(sessao_db):
    """Criterio 2: mais Pokemon do que cabe numa pagina; o total nao muda."""
    sessao = _registrar("Misty")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])

    for _ in range(5):
        sessao_db.add(
            PokemonInstancia(
                laboratorio_id=laboratorio_id,
                especie_id=1,
                nivel=5,
                experiencia=0,
                hp_atual_pct=100,
                origem="CAPTURADO",
                capturado_em=datetime.now(UTC),
            )
        )
    sessao_db.commit()

    pagina1 = client.get(
        "/pokemon", params={"page": 1, "page_size": 5}, headers=_cabecalho(sessao)
    ).json()
    pagina2 = client.get(
        "/pokemon", params={"page": 2, "page_size": 5}, headers=_cabecalho(sessao)
    ).json()

    assert pagina1["total"] == pagina2["total"] == 8
    assert len(pagina1["items"]) == 5
    assert len(pagina2["items"]) == 3
    ids_pagina1 = {item["id"] for item in pagina1["items"]}
    ids_pagina2 = {item["id"] for item in pagina2["items"]}
    assert ids_pagina1.isdisjoint(ids_pagina2)


def test_ficha_de_pokemon_nivel_5_mostra_stats_do_nivel_5(sessao_db):
    """Criterio 5: Bulbasaur nivel 5 -> hp 19, atk/def 9, spa/spd 11, spe 9."""
    sessao = _registrar("Brock")
    lista = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    bulbasaur_id = next(item["id"] for item in lista["items"] if item["especie_id"] == 1)

    resposta = client.get(f"/pokemon/{bulbasaur_id}", headers=_cabecalho(sessao))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["stats"] == {
        "hp": 19,
        "ataque": 9,
        "defesa": 9,
        "ataque_especial": 11,
        "defesa_especial": 11,
        "velocidade": 9,
    }
    assert corpo["hp_atual"] == 19
    assert corpo["hp_maximo"] == 19
    assert corpo["nivel_maximo"] is False
    assert isinstance(corpo["experiencia_para_proximo_nivel"], int)
    assert corpo["experiencia_para_proximo_nivel"] > 0


def test_ficha_no_nivel_maximo_informa_que_nao_ha_proximo_nivel(sessao_db):
    """Criterio 6: nivel maximo nunca mostra um numero, mostra o fato."""
    sessao = _registrar("Gary")
    lista = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    pokemon_id = lista["items"][0]["id"]

    instancia = sessao_db.get(PokemonInstancia, uuid.UUID(pokemon_id))
    instancia.nivel = balance.NIVEL_MAXIMO
    instancia.experiencia = 999_999_999
    sessao_db.commit()

    resposta = client.get(f"/pokemon/{pokemon_id}", headers=_cabecalho(sessao))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["nivel_maximo"] is True
    assert corpo["experiencia_para_proximo_nivel"] is None


def test_apelido_aparece_na_lista_e_na_ficha_e_apagar_devolve_o_nome_da_especie(sessao_db):
    """Criterio 7."""
    sessao = _registrar("May")
    lista = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    pokemon_id = lista["items"][0]["id"]
    especie_nome = lista["items"][0]["especie_nome"]

    renomear = client.patch(
        f"/pokemon/{pokemon_id}", json={"apelido": "Fofinho"}, headers=_cabecalho(sessao)
    )
    assert renomear.status_code == 200
    assert renomear.json()["nome"] == "Fofinho"

    lista_depois = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    item = next(i for i in lista_depois["items"] if i["id"] == pokemon_id)
    assert item["nome"] == "Fofinho"

    limpar = client.patch(
        f"/pokemon/{pokemon_id}", json={"apelido": None}, headers=_cabecalho(sessao)
    )
    assert limpar.status_code == 200
    assert limpar.json()["nome"] == especie_nome


def test_apelido_composto_so_de_espacos_e_recusado(sessao_db):
    sessao = _registrar("Dawn")
    lista = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    pokemon_id = lista["items"][0]["id"]

    resposta = client.patch(
        f"/pokemon/{pokemon_id}", json={"apelido": "   "}, headers=_cabecalho(sessao)
    )

    assert resposta.status_code == 422


def test_apelido_acima_de_cinquenta_caracteres_e_recusado(sessao_db):
    sessao = _registrar("Lucas")
    lista = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    pokemon_id = lista["items"][0]["id"]

    resposta = client.patch(
        f"/pokemon/{pokemon_id}", json={"apelido": "x" * 51}, headers=_cabecalho(sessao)
    )

    assert resposta.status_code == 422


def test_pokemon_inexistente_devolve_404(sessao_db):
    sessao = _registrar("Barry")

    resposta = client.get(f"/pokemon/{uuid.uuid4()}", headers=_cabecalho(sessao))

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"


def test_filtro_tipo_invalido_devolve_422(sessao_db):
    sessao = _registrar("Dawn2")

    resposta = client.get("/pokemon", params={"tipo": "nao-existe"}, headers=_cabecalho(sessao))

    assert resposta.status_code == 422


def test_sem_token_devolve_401(sessao_db):
    assert client.get("/pokemon").status_code == 401
