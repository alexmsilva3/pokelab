"""Hash de senha, token de sessao e a guarda de producao (spec 002, tarefa 5)."""

from __future__ import annotations

import time
import uuid

import pytest
from jose import jwt

from app.core import seguranca
from app.core.config import SECRET_KEYS_PUBLICAS, Settings, get_settings, validar_producao
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


# --- CRITICO: a chave do .env.example passava pela guarda de producao ------
# (regressao da revisao adversarial da Fase 2)
# validar_producao so recusava a literal "desenvolvimento-apenas", mas um
# deploy feito com `make setup` usa a chave do .env.example, que e publica.


def _settings(**sobrescritas) -> Settings:
    base = {
        "environment": "production",
        "secret_key": "x" * 48,
        "postgres_user": "u",
        "postgres_password": "p",
        "postgres_db": "d",
        "postgres_host": "h",
    }
    base.update(sobrescritas)
    return Settings(_env_file=None, **base)


@pytest.mark.parametrize("chave", sorted(SECRET_KEYS_PUBLICAS))
def test_producao_recusa_qualquer_chave_publicada_no_repositorio(chave):
    with pytest.raises(RuntimeError, match="publicado no repositorio"):
        validar_producao(_settings(secret_key=chave))


def test_chave_do_env_example_e_recusada_em_producao():
    # A regressao exata: esta e a string distribuida em .env.example.
    with pytest.raises(RuntimeError):
        validar_producao(_settings(secret_key="trocar-em-producao-chave-longa-e-aleatoria"))


def test_producao_recusa_chave_curta_demais():
    with pytest.raises(RuntimeError, match="minimo em producao"):
        validar_producao(_settings(secret_key="chave-propria-porem-curta"))


def test_producao_aceita_chave_propria_e_longa():
    validar_producao(_settings(secret_key="k" * 64))


def test_desenvolvimento_nao_e_barrado_pela_guarda():
    validar_producao(_settings(environment="development", secret_key="desenvolvimento-apenas"))
