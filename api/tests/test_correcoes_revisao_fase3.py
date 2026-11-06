"""Regressao dos defeitos encontrados na revisao adversarial da Fase 3.

Cada teste nasceu de um achado concreto; o comentario de cada bloco diz qual.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.database import engine
from app.game import balance
from app.game.stats import hp_atual_absoluto
from app.main import app
from app.routers.pokemon import PAGE_MAXIMA

cliente = TestClient(app)


def _banco_disponivel() -> bool:
    try:
        with engine.connect():
            return True
    except OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _banco_disponivel(), reason="Postgres indisponivel; rode com make test-db"
)


def _registrar() -> str:
    usuario = f"f3_{uuid.uuid4().hex[:10]}"
    resposta = cliente.post("/auth/register", json={"usuario": usuario, "senha": "senhavalida123"})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["token"]


def _cabecalho(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- ALTO: page sem teto estourava o OFFSET do Postgres -------------------
# (page - 1) * page_size passava de 2^63-1, o Postgres recusava o OFFSET e a
# resposta era 500 em texto puro, fora do envelope da aplicacao.


def test_pagina_absurda_e_recusada_sem_derrubar_o_servidor():
    token = _registrar()
    resposta = cliente.get(
        "/pokemon", params={"page": 4611686018427387904}, headers=_cabecalho(token)
    )
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "ENTRADA_INVALIDA"


def test_pagina_no_limite_maximo_ainda_responde():
    token = _registrar()
    resposta = cliente.get("/pokemon", params={"page": PAGE_MAXIMA}, headers=_cabecalho(token))
    assert resposta.status_code == 200
    assert resposta.json()["items"] == []


def test_pagina_alem_do_fim_devolve_lista_vazia_e_total_correto():
    token = _registrar()
    resposta = cliente.get("/pokemon", params={"page": 99}, headers=_cabecalho(token))
    corpo = resposta.json()

    assert resposta.status_code == 200
    assert corpo["items"] == []
    # O total continua sendo o do acervo, para a interface saber que a pagina e
    # que esta fora de faixa, e nao o filtro que nao achou nada.
    assert corpo["total"] == len(balance.STARTER_SPECIES_IDS)


# --- ALTO: hp_atual com pct zero divergia do SDD --------------------------
# O documento dizia max(1, ...) sem excecao. A regra correta e a do codigo
# (nocauteado e nocauteado) e o SDD 4.2 foi atualizado junto, como manda o
# Artigo VIII. Estes testes fixam a regra nas duas pontas.


def test_pct_zero_significa_nocauteado_e_nao_um_ponto_de_hp():
    assert hp_atual_absoluto(105, 0) == 0


def test_pct_positivo_nunca_arredonda_para_zero():
    # Um Pokemon a 1% de um HP alto esta machucado, nao nocauteado: mostrar 0
    # na ficha faria o professor achar que ele caiu.
    assert hp_atual_absoluto(200, 1) >= balance.HP_MINIMO_VIVO


def test_hp_atual_nunca_passa_do_maximo():
    assert hp_atual_absoluto(19, 100) == 19


# --- BAIXO: o cliente deduzia "tem apelido" comparando nome com especie ---
# A deducao errava quem apelidasse um Pidgey de "Pidgey": o campo aparecia
# vazio e o proximo salvar apagaria o apelido.


def test_a_ficha_devolve_o_apelido_cru_alem_do_nome_resolvido():
    token = _registrar()
    primeiro = cliente.get("/pokemon", headers=_cabecalho(token)).json()["items"][0]

    sem_apelido = cliente.get(f"/pokemon/{primeiro['id']}", headers=_cabecalho(token)).json()
    assert sem_apelido["apelido"] is None
    assert sem_apelido["nome"] == sem_apelido["especie_nome"]

    especie = sem_apelido["especie_nome"]
    cliente.patch(
        f"/pokemon/{primeiro['id']}", json={"apelido": especie}, headers=_cabecalho(token)
    )
    com_apelido = cliente.get(f"/pokemon/{primeiro['id']}", headers=_cabecalho(token)).json()

    # O caso que quebrava a deducao: apelido identico ao nome da especie.
    assert com_apelido["apelido"] == especie
    assert com_apelido["nome"] == especie


def test_apelido_cru_volta_a_ser_nulo_quando_limpo():
    token = _registrar()
    primeiro = cliente.get("/pokemon", headers=_cabecalho(token)).json()["items"][0]

    cliente.patch(
        f"/pokemon/{primeiro['id']}", json={"apelido": "Folhinha"}, headers=_cabecalho(token)
    )
    limpo = cliente.patch(
        f"/pokemon/{primeiro['id']}", json={"apelido": None}, headers=_cabecalho(token)
    ).json()

    assert limpo["apelido"] is None
    assert limpo["nome"] == limpo["especie_nome"]


def test_apelido_cru_aparece_tambem_na_listagem():
    token = _registrar()
    primeiro = cliente.get("/pokemon", headers=_cabecalho(token)).json()["items"][0]
    assert "apelido" in primeiro

    cliente.patch(
        f"/pokemon/{primeiro['id']}", json={"apelido": "Folhinha"}, headers=_cabecalho(token)
    )
    lista = cliente.get("/pokemon", headers=_cabecalho(token)).json()["items"]
    renomeado = next(item for item in lista if item["id"] == primeiro["id"])

    assert renomeado["apelido"] == "Folhinha"
    assert renomeado["nome"] == "Folhinha"


# --- MEDIO: nivel fora de faixa recusado com envelope, nao com 500 --------


@pytest.mark.parametrize("parametros", [{"nivel_min": 0}, {"nivel_max": 0}, {"nivel_min": 101}])
def test_nivel_fora_de_faixa_devolve_envelope_de_entrada_invalida(parametros):
    token = _registrar()
    resposta = cliente.get("/pokemon", params=parametros, headers=_cabecalho(token))
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "ENTRADA_INVALIDA"


def test_nivel_minimo_maior_que_maximo_devolve_lista_vazia_e_nao_erro():
    token = _registrar()
    resposta = cliente.get(
        "/pokemon", params={"nivel_min": 50, "nivel_max": 10}, headers=_cabecalho(token)
    )
    assert resposta.status_code == 200
    assert resposta.json()["items"] == []
