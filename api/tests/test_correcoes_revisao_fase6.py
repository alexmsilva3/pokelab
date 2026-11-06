"""Regressao dos defeitos encontrados na revisao adversarial da Fase 6."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.database import SessionLocal, engine
from app.game import expedition
from app.main import app
from app.models import Expedicao

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


def _preparar() -> tuple[dict[str, str], str]:
    """Registra um professor e devolve o cabecalho e uma expedicao em curso."""
    usuario = f"f6_{uuid.uuid4().hex[:10]}"
    token = cliente.post(
        "/auth/register", json={"usuario": usuario, "senha": "senhavalida123"}
    ).json()["token"]
    cabecalho = {"Authorization": f"Bearer {token}"}

    treinador = cliente.get("/trainers", headers=cabecalho).json()["items"][0]
    pokemon = cliente.get("/pokemon", headers=cabecalho).json()["items"][0]
    cliente.put(
        f"/trainers/{treinador['id']}/team",
        json={"pokemon_ids": [pokemon["id"]]},
        headers=cabecalho,
    )
    expedicao = cliente.post(
        "/expeditions",
        json={"treinador_id": treinador["id"], "local_id": "route-1", "carga": []},
        headers=cabecalho,
    )
    assert expedicao.status_code == 201, expedicao.text
    return cabecalho, expedicao.json()["id"]


def _vencer(expedicao_id: str) -> None:
    """Empurra o eta para o passado, sem mexer na coluna de status."""
    with SessionLocal() as sessao:
        expedicao = sessao.get(Expedicao, uuid.UUID(expedicao_id))
        expedicao.eta = datetime.now(UTC) - timedelta(minutes=5)
        sessao.commit()


# --- CRITICO: a expedicao sumia da tela no instante em que terminava ------
# O cliente pedia ?status=EM_CURSO acreditando filtrar a coluna gravada; o
# servidor filtra o estado OBSERVADO. Vencido o eta, a expedicao deixava de
# ser EM_CURSO observado e desaparecia — justamente quando o professor mais
# quer olhar para ela.


def test_expedicao_vencida_sai_do_filtro_de_em_curso():
    cabecalho, expedicao_id = _preparar()
    _vencer(expedicao_id)

    em_curso = cliente.get("/expeditions", params={"status": "EM_CURSO"}, headers=cabecalho).json()
    assert [i["id"] for i in em_curso["items"]] == []


def test_filtro_aceita_varios_estados_e_mantem_a_vencida_visivel():
    cabecalho, expedicao_id = _preparar()
    _vencer(expedicao_id)

    resposta = cliente.get(
        "/expeditions",
        params=[("status", "EM_CURSO"), ("status", "AGUARDANDO_RELATORIO")],
        headers=cabecalho,
    ).json()

    assert expedicao_id in [i["id"] for i in resposta["items"]]
    item = next(i for i in resposta["items"] if i["id"] == expedicao_id)
    assert item["estado_observado"] == "AGUARDANDO_RELATORIO"


def test_a_coluna_gravada_continua_em_curso_depois_do_prazo():
    # O estado e derivado, nao gravado: nenhuma escrita aconteceu no banco.
    cabecalho, expedicao_id = _preparar()
    _vencer(expedicao_id)

    cliente.get(f"/expeditions/{expedicao_id}", headers=cabecalho)

    with SessionLocal() as sessao:
        gravado = sessao.get(Expedicao, uuid.UUID(expedicao_id)).status
    assert gravado == expedition.StatusExpedicao.EM_CURSO


# --- BAIXO: prazo de uma viagem que nao vai mais acontecer ----------------


def test_expedicao_abortada_nao_informa_tempo_restante():
    cabecalho, expedicao_id = _preparar()
    abortada = cliente.delete(f"/expeditions/{expedicao_id}", headers=cabecalho).json()

    assert abortada["estado_observado"] == "ABORTADA"
    assert abortada["segundos_restantes"] is None


def test_expedicao_em_curso_continua_informando_tempo_restante():
    cabecalho, _ = _preparar()
    ativa = cliente.get("/expeditions", params={"status": "EM_CURSO"}, headers=cabecalho).json()[
        "items"
    ][0]

    assert isinstance(ativa["segundos_restantes"], int)
    assert ativa["segundos_restantes"] >= 0


# --- ALTO: a previa recusada devolve nulos, nao zeros ---------------------
# O tipo do cliente declarava os cinco campos como obrigatorios, e a tela
# desenhava "Chance estimada: 0%" ao lado do motivo da recusa.


def test_previa_recusada_devolve_nulo_em_todo_campo_numerico():
    usuario = f"f6p_{uuid.uuid4().hex[:10]}"
    token = cliente.post(
        "/auth/register", json={"usuario": usuario, "senha": "senhavalida123"}
    ).json()["token"]
    cabecalho = {"Authorization": f"Bearer {token}"}
    treinador = cliente.get("/trainers", headers=cabecalho).json()["items"][0]

    previa = cliente.post(
        "/expeditions/preview",
        json={"treinador_id": treinador["id"], "local_id": "route-1", "carga": []},
        headers=cabecalho,
    ).json()

    assert previa["valido"] is False
    assert previa["codigo"] == "TIME_VAZIO"
    assert previa["motivo"]
    for campo in (
        "duracao_minutos",
        "eta_estimado",
        "dificuldade",
        "chance_estimada",
        "capacidade_bagagem",
    ):
        assert previa[campo] is None, campo
