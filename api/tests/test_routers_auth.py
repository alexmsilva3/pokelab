"""Contrato HTTP de /auth/register, /auth/login e /me (spec 002, tarefas 7 e 8)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import requer_banco

pytestmark = requer_banco

client = TestClient(app)


def test_registrar_devolve_201_com_token_e_laboratorio(sessao_db):
    resposta = client.post(
        "/auth/register",
        json={"usuario": "Dawn", "senha": "piplup123456", "nome_exibicao": "Dawn Berlitz"},
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["token"]
    assert corpo["professor"]["usuario"] == "Dawn"
    assert corpo["laboratorio"]["nivel"] == 1
    assert corpo["laboratorio"]["moedas"] == 0


def test_registrar_usuario_repetido_em_qualquer_caixa_devolve_409(sessao_db):
    client.post("/auth/register", json={"usuario": "Paul", "senha": "chimchar1234"})
    resposta = client.post("/auth/register", json={"usuario": "PAUL", "senha": "outrasenha12"})
    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "USUARIO_EM_USO"


def test_registrar_senha_curta_devolve_422_e_nao_cria_nada(sessao_db):
    resposta = client.post("/auth/register", json={"usuario": "Barry", "senha": "curta"})
    assert resposta.status_code == 422

    login = client.post("/auth/login", json={"usuario": "Barry", "senha": "curta"})
    assert login.status_code == 401  # ninguem foi criado


def test_login_credenciais_corretas_devolve_token(sessao_db):
    client.post("/auth/register", json={"usuario": "Lucas", "senha": "empoleon1234"})
    resposta = client.post("/auth/login", json={"usuario": "lucas", "senha": "empoleon1234"})
    assert resposta.status_code == 200
    assert resposta.json()["token"]


def test_login_senha_errada_e_usuario_inexistente_devolvem_401_identico(sessao_db):
    client.post("/auth/register", json={"usuario": "Kenny", "senha": "prinplup123"})
    senha_errada = client.post("/auth/login", json={"usuario": "Kenny", "senha": "senha-errada"})
    usuario_inexistente = client.post(
        "/auth/login", json={"usuario": "ninguem-aqui", "senha": "qualquer-coisa"}
    )
    assert senha_errada.status_code == 401
    assert usuario_inexistente.status_code == 401
    assert senha_errada.json() == usuario_inexistente.json()


def test_me_com_token_devolve_tres_pokemon_e_um_treinador(sessao_db):
    registro = client.post("/auth/register", json={"usuario": "May", "senha": "torchic123456"})
    token = registro.json()["token"]

    resposta = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resposta.status_code == 200
    resumo = resposta.json()["resumo"]
    assert resumo["pokemon"] == 3
    assert resumo["treinadores"] == 1
    assert resumo["locais_desbloqueados"] == 1
    assert resumo["especies_vistas"] == 3
    assert resumo["especies_capturadas"] == 3


def test_me_sem_token_devolve_401(sessao_db):
    resposta = client.get("/me")
    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "NAO_AUTENTICADO"


def test_me_com_token_invalido_devolve_401(sessao_db):
    resposta = client.get("/me", headers={"Authorization": "Bearer token-forjado"})
    assert resposta.status_code == 401


def test_nenhuma_resposta_vaza_senha_ou_hash(sessao_db):
    registro = client.post("/auth/register", json={"usuario": "Drew", "senha": "roselia123456"})
    token = registro.json()["token"]
    perfil = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    for resposta in (registro, perfil):
        texto = json.dumps(resposta.json())
        assert "senha_hash" not in texto
        assert "roselia123456" not in texto
