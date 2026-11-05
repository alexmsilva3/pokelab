"""Hash de senha e token de sessao (spec 002, tarefa 5)."""

from __future__ import annotations

import time
import uuid

import pytest
from jose import jwt

from app.core import seguranca
from app.core.config import get_settings
from app.core.erros import NaoAutenticado


def test_hash_senha_confere_com_a_mesma_senha():
    hash_ = seguranca.hash_senha("pikachu123")
    assert seguranca.verificar_senha("pikachu123", hash_)


def test_hash_senha_recusa_senha_errada():
    hash_ = seguranca.hash_senha("pikachu123")
    assert not seguranca.verificar_senha("outra-senha-qualquer", hash_)


def test_hash_senha_nao_guarda_a_senha_em_texto_legivel():
    assert "pikachu123" not in seguranca.hash_senha("pikachu123")


def test_hash_descartavel_nunca_confere_com_senha_nenhuma():
    assert not seguranca.verificar_senha("qualquer-coisa", seguranca.HASH_DESCARTAVEL)


def test_emitir_e_validar_token_devolve_o_mesmo_professor():
    professor_id = uuid.uuid4()
    token = seguranca.emitir_token(professor_id)
    assert seguranca.validar_token(token) == professor_id


def test_token_assinado_com_outra_chave_e_rejeitado():
    token_forjado = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": time.time() + 3600},
        "chave-que-nao-e-a-do-servidor",
        algorithm=seguranca.ALGORITMO_TOKEN,
    )
    with pytest.raises(NaoAutenticado):
        seguranca.validar_token(token_forjado)


def test_token_expirado_e_rejeitado():
    settings = get_settings()
    token_expirado = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": time.time() - 10},
        settings.secret_key,
        algorithm=seguranca.ALGORITMO_TOKEN,
    )
    with pytest.raises(NaoAutenticado):
        seguranca.validar_token(token_expirado)


def test_token_malformado_e_rejeitado():
    with pytest.raises(NaoAutenticado):
        seguranca.validar_token("isto-nao-e-um-jwt")


def test_token_sem_sub_e_rejeitado():
    settings = get_settings()
    token_sem_sub = jwt.encode(
        {"exp": time.time() + 3600}, settings.secret_key, algorithm=seguranca.ALGORITMO_TOKEN
    )
    with pytest.raises(NaoAutenticado):
        seguranca.validar_token(token_sem_sub)


def test_token_com_sub_que_nao_e_uuid_e_rejeitado():
    settings = get_settings()
    token_invalido = jwt.encode(
        {"sub": "nao-sou-um-uuid", "exp": time.time() + 3600},
        settings.secret_key,
        algorithm=seguranca.ALGORITMO_TOKEN,
    )
    with pytest.raises(NaoAutenticado):
        seguranca.validar_token(token_invalido)
