"""Regressao dos defeitos encontrados na revisao adversarial da Fase 2.

Cada teste aqui nasceu de um achado concreto. Eles existem para que o mesmo
defeito nao volte, e o comentario de cada bloco diz qual era.
"""

from __future__ import annotations

import threading
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.core.config import SECRET_KEYS_PUBLICAS, Settings, validar_producao
from app.core.database import SessionLocal, engine
from app.core.erros import KitJaConcedido
from app.game import balance
from app.game.laboratorio import limite_treinadores
from app.main import app
from app.models import Laboratorio, PokemonInstancia, Treinador
from app.services import auth as auth_service

cliente = TestClient(app)


def _banco_disponivel() -> bool:
    try:
        with engine.connect():
            return True
    except OperationalError:
        return False


def _usuario_unico(prefixo: str) -> str:
    return f"{prefixo}_{uuid.uuid4().hex[:10]}"


# --- CRITICO: 422 devolvia a senha em texto claro --------------------------
# Nao havia handler de RequestValidationError, entao o 422 do Pydantic ecoava
# o valor rejeitado no campo `input` — a senha voltava no corpo da resposta e
# dali para log de proxy, APM e devtools.


@pytest.mark.parametrize(
    ("caminho", "corpo", "senha"),
    [
        ("/auth/register", {"usuario": "professor_x", "senha": "curta12"}, "curta12"),
        ("/auth/register", {"usuario": "professor_y", "senha": "a" * 200}, "a" * 200),
        ("/auth/login", {"usuario": "professor_z", "senha": ""}, None),
    ],
)
def test_erro_de_validacao_nunca_devolve_a_senha_enviada(caminho, corpo, senha):
    resposta = cliente.post(caminho, json=corpo)
    assert resposta.status_code == 422
    texto = resposta.text
    if senha:
        assert senha not in texto
    assert '"input"' not in texto


def test_erro_de_validacao_sai_no_envelope_da_aplicacao():
    # Antes o 422 escapava do envelope {"erro": {...}} e chegava ao professor
    # como texto de protocolo em ingles.
    resposta = cliente.post("/auth/register", json={"usuario": "ab", "senha": "senhavalida1"})
    corpo = resposta.json()

    assert resposta.status_code == 422
    assert corpo["erro"]["codigo"] == "ENTRADA_INVALIDA"
    assert corpo["erro"]["mensagem"]
    assert "detail" not in corpo


def test_erro_de_validacao_diz_qual_campo_falhou_sem_o_valor():
    resposta = cliente.post("/auth/register", json={"usuario": "ok_assim", "senha": "curta"})
    campos = resposta.json()["erro"]["detalhes"]["campos"]

    assert any(campo["campo"] == "senha" for campo in campos)
    assert all("input" not in campo for campo in campos)
    # O contexto de um campo sensivel tambem nao volta: `ctx` carrega o limite,
    # mas em outros validadores pode carregar o valor.
    senha = next(campo for campo in campos if campo["campo"] == "senha")
    assert "contexto" not in senha


# --- CRITICO: a chave do .env.example passava pela guarda de producao ------
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


# --- ALTO: concessao do kit sem lock nem checagem de status ----------------
# `starters_concedidos` era escrito e nunca lido. Uma segunda concessao sobre
# o MESMO laboratorio adicionava tres Pokemon e um treinador extras antes de
# estourar na chave composta de item_estoques, com IntegrityError vazando.

pytestmark_banco = pytest.mark.skipif(
    not _banco_disponivel(), reason="Postgres indisponivel; rode com make test-db"
)


@pytestmark_banco
def test_segunda_concessao_do_kit_e_recusada():
    with SessionLocal() as sessao:
        criada = auth_service.registrar(
            sessao, usuario=_usuario_unico("kit2x"), senha="senhavalida123"
        )
        laboratorio = sessao.get(Laboratorio, criada.laboratorio.id)

        with pytest.raises(KitJaConcedido):
            auth_service._conceder_kit(sessao, laboratorio)
        sessao.rollback()


@pytestmark_banco
def test_segunda_concessao_nao_cria_pokemon_nem_treinador_extra():
    with SessionLocal() as sessao:
        criada = auth_service.registrar(
            sessao, usuario=_usuario_unico("kitextra"), senha="senhavalida123"
        )
        laboratorio_id = criada.laboratorio.id

        def contar(modelo) -> int:
            return len(
                sessao.scalars(select(modelo).where(modelo.laboratorio_id == laboratorio_id)).all()
            )

        antes = (contar(PokemonInstancia), contar(Treinador))

        with pytest.raises(KitJaConcedido):
            auth_service._conceder_kit(sessao, sessao.get(Laboratorio, laboratorio_id))
        sessao.rollback()

        assert (contar(PokemonInstancia), contar(Treinador)) == antes
        assert antes == (len(balance.STARTER_SPECIES_IDS), balance.TREINADORES_NO_KIT_INICIAL)


@pytestmark_banco
def test_registros_concorrentes_com_o_mesmo_usuario_rendem_uma_conta_so():
    usuario = _usuario_unico("corrida")
    resultados: list[str] = []
    barreira = threading.Barrier(2)

    def registrar() -> None:
        barreira.wait()
        with SessionLocal() as sessao:
            try:
                auth_service.registrar(sessao, usuario=usuario, senha="senhavalida123")
                resultados.append("ok")
            except Exception as erro:  # o tipo exato e justamente o que se afere
                resultados.append(type(erro).__name__)

    threads = [threading.Thread(target=registrar) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert resultados.count("ok") == 1, resultados


# --- ALTO: a semente do kit nao era gravada --------------------------------
# O servico chamava random.Random() sem semente, contrariando o Artigo III: o
# kit de um laboratorio existente nao podia ser remontado.


@pytestmark_banco
def test_semente_do_kit_fica_gravada_no_laboratorio():
    with SessionLocal() as sessao:
        criada = auth_service.registrar(
            sessao, usuario=_usuario_unico("semente"), senha="senhavalida123"
        )
        laboratorio = sessao.get(Laboratorio, criada.laboratorio.id)

        assert laboratorio.semente_kit_inicial is not None
        assert 0 <= laboratorio.semente_kit_inicial < auth_service.SEMENTE_MAXIMA


@pytestmark_banco
def test_a_semente_gravada_remonta_o_mesmo_kit():
    import random

    from app.game.kit_inicial import EspecieInicial, montar_kit_inicial
    from app.repositories import especies as especies_repo

    with SessionLocal() as sessao:
        criada = auth_service.registrar(
            sessao, usuario=_usuario_unico("remonta"), senha="senhavalida123"
        )
        laboratorio = sessao.get(Laboratorio, criada.laboratorio.id)

        especies = [
            EspecieInicial(id=e.id, nome=e.nome, curva_crescimento=e.curva_crescimento)
            for e in especies_repo.buscar_iniciais(sessao)
        ]
        remontado = montar_kit_inicial(especies, random.Random(laboratorio.semente_kit_inicial))

        treinador_no_banco = sessao.scalars(
            select(Treinador).where(Treinador.laboratorio_id == laboratorio.id)
        ).first()
        assert remontado.treinadores[0].nome == treinador_no_banco.nome


# --- BAIXO: usuario composto so de espacos era aceito ----------------------


@pytest.mark.parametrize("usuario", ["   ", "\t\t\t", "    \n  "])
def test_usuario_so_com_espacos_e_recusado(usuario):
    resposta = cliente.post("/auth/register", json={"usuario": usuario, "senha": "senhavalida123"})
    assert resposta.status_code == 422


@pytestmark_banco
def test_espacos_nas_pontas_do_usuario_sao_aparados():
    nome = _usuario_unico("aparado")
    resposta = cliente.post(
        "/auth/register", json={"usuario": f"  {nome}  ", "senha": "senhavalida123"}
    )
    assert resposta.status_code == 201
    assert resposta.json()["professor"]["usuario"] == nome


# --- MEDIO: limite_treinadores nao existia ---------------------------------
# O invariante 5 do SDD pede o limite derivado do nivel, e nao havia funcao,
# coluna nem campo de resposta que o calculasse.


@pytestmark_banco
def test_me_informa_quantos_treinadores_o_laboratorio_comporta():
    nome = _usuario_unico("limite")
    registro = cliente.post("/auth/register", json={"usuario": nome, "senha": "senhavalida123"})
    token = registro.json()["token"]

    perfil = cliente.get("/me", headers={"Authorization": f"Bearer {token}"}).json()

    assert perfil["laboratorio"]["limite_treinadores"] == limite_treinadores(1)
    assert perfil["laboratorio"]["limite_treinadores"] == balance.LIMITE_TREINADORES_NIVEL_1


@pytestmark_banco
def test_o_kit_inicial_nao_estoura_o_limite_do_laboratorio_novo():
    nome = _usuario_unico("cabe")
    registro = cliente.post("/auth/register", json={"usuario": nome, "senha": "senhavalida123"})
    token = registro.json()["token"]

    perfil = cliente.get("/me", headers={"Authorization": f"Bearer {token}"}).json()

    assert perfil["resumo"]["treinadores"] <= perfil["laboratorio"]["limite_treinadores"]
