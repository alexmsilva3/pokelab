"""Regressao dos defeitos encontrados na revisao adversarial da Fase 7.

Cada teste nasceu de um achado concreto; o comentario de cada bloco diz qual.
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.database import SessionLocal, engine
from app.main import app
from app.models import Expedicao, PokemonInstancia
from app.repositories import laboratorios as laboratorios_repo
from app.services import expedicoes as expedicoes_service

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

LOCAL_ROUTE_1 = "route-1"  # so Pidgey (16) e Rattata (19) na tabela de encontros


def _registrar(prefixo: str) -> dict:
    usuario = f"{prefixo}_{uuid.uuid4().hex[:10]}"
    resposta = cliente.post("/auth/register", json={"usuario": usuario, "senha": "senhavalida123"})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _cabecalho(sessao: dict) -> dict:
    return {"Authorization": f"Bearer {sessao['token']}"}


def _treinador_pronto(sessao: dict) -> str:
    """O primeiro treinador do laboratorio, com um Pokemon no time."""
    treinador_id = cliente.get("/trainers", headers=_cabecalho(sessao)).json()["items"][0]["id"]
    pokemon_resposta = cliente.get(
        "/pokemon", params={"livre": True}, headers=_cabecalho(sessao)
    ).json()
    pokemon_id = pokemon_resposta["items"][0]["id"]
    resposta = cliente.put(
        f"/trainers/{treinador_id}/team",
        json={"pokemon_ids": [pokemon_id]},
        headers=_cabecalho(sessao),
    )
    assert resposta.status_code == 200, resposta.text
    return treinador_id


def _despachar(sessao: dict, treinador_id: str, local_id: str = LOCAL_ROUTE_1) -> dict:
    resposta = cliente.post(
        "/expeditions",
        json={"treinador_id": treinador_id, "local_id": local_id, "carga": []},
        headers=_cabecalho(sessao),
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def _abortar(sessao: dict, expedicao_id: str):
    return cliente.delete(f"/expeditions/{expedicao_id}", headers=_cabecalho(sessao))


# --- Achado 1 (ALTO): o lock do laboratorio devolvia objeto obsoleto ---------
#
# `professor_atual` ja carrega o `Laboratorio` da sessao da requisicao ANTES
# de qualquer lock. Sem `populate_existing=True` no `SELECT ... FOR UPDATE` de
# `laboratorios_repo.travar`, o SQLAlchemy devolvia o objeto do identity map
# sem atualizar os atributos: o lock da linha era real, mas o valor lido era o
# de antes dele. Tres escritores concorrentes liam a mesma `experiencia` de
# partida e so o ultimo commit vencia — os outros dois ganhos eram perdidos em
# silencio.
#
# Reproduzido sem depender do resultado probabilistico de uma expedicao de
# verdade: simula exatamente a condicao real (uma sessao "de requisicao" que
# carrega o laboratorio do jeito que `professor_atual` carrega, e so depois
# pede o lock), com tres threads somando um valor conhecido sob
# `threading.Barrier`.


def test_travar_laboratorio_enxerga_a_experiencia_mais_recente_sob_concorrencia(sessao_db):
    sessao = _registrar("Achado1")
    professor_id = uuid.UUID(sessao["professor"]["id"])
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])

    partida = threading.Barrier(3)
    resultados: list[int] = []
    trava = threading.Lock()

    def incrementar() -> None:
        with SessionLocal() as sessao_local:
            # Exatamente o que `professor_atual` faz em TODA rota autenticada,
            # antes de qualquer lock ser pedido: carrega o MESMO laboratorio.
            pre_lock = laboratorios_repo.buscar_por_professor_id(sessao_local, professor_id)
            assert pre_lock is not None
            partida.wait()

            travado = laboratorios_repo.travar(sessao_local, laboratorio_id)
            assert travado is not None
            nova_experiencia = travado.experiencia + 10
            laboratorios_repo.atualizar_progressao(
                travado, nivel=travado.nivel, experiencia=nova_experiencia
            )
            sessao_local.commit()
            with trava:
                resultados.append(nova_experiencia)

    threads = [threading.Thread(target=incrementar) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    final = laboratorios_repo.buscar_por_id(sessao_db, laboratorio_id)
    sessao_db.refresh(final)
    # Sem o lock refletindo o estado mais recente, as tres threads leriam a
    # mesma experiencia de partida (0) e a gravada final seria 10, nao 30:
    # duas somas de 10 desapareceriam.
    assert sorted(resultados) == [10, 20, 30], resultados
    assert final.experiencia == 30


# --- Achado 2 (MEDIO): o aborto creditava o tempo de campo como enfermaria --
#
# `abortar()` devolvia o treinador para DISPONIVEL sem recarimbar
# `hp_atualizado_em` de nenhum Pokemon do time. Como o carimbo continuava
# sendo o instante da PARTIDA, a leitura seguinte creditava de uma vez todo o
# tempo passado em campo, como se o Pokemon tivesse ficado parado no
# laboratorio o tempo todo.


def test_abortar_recarimba_hp_atualizado_em_sem_mudar_o_hp_gravado(sessao_db):
    sessao = _registrar("Achado2")
    treinador_id = _treinador_pronto(sessao)
    ficha = cliente.get(f"/trainers/{treinador_id}", headers=_cabecalho(sessao)).json()
    pokemon_id = uuid.UUID(ficha["time"][0]["id"])
    despacho = _despachar(sessao, treinador_id)

    # Simula 120 minutos de campo com o time a 40%: empurra o carimbo bem para
    # tras, exatamente o estado que o bug deixava intocado no aborto.
    with SessionLocal() as sessao_local:
        pokemon = sessao_local.get(PokemonInstancia, pokemon_id)
        pokemon.hp_atual_pct = 40
        pokemon.hp_atualizado_em = datetime.now(UTC) - timedelta(minutes=120)
        sessao_local.commit()

    antes_do_aborto = datetime.now(UTC)
    resposta = _abortar(sessao, despacho["id"])
    assert resposta.status_code == 200

    with SessionLocal() as sessao_local:
        pokemon = sessao_local.get(PokemonInstancia, pokemon_id)
        # So o marco muda; o HP gravado continua exatamente o que estava.
        assert pokemon.hp_atual_pct == 40
        assert pokemon.hp_atualizado_em >= antes_do_aborto

    # A leitura seguinte nao pode mostrar HP recuperado: o marco acabou de ser
    # zerado, entao praticamente nenhum tempo se passou desde ele.
    ficha = cliente.get(f"/trainers/{treinador_id}", headers=_cabecalho(sessao)).json()
    assert ficha["time"][0]["hp_atual_pct"] == 40


# --- Achado 3 (BAIXO, decisao de arquitetura): especies_vistas fora do retrato
#
# `_montar_contexto` lia `pokedex_repo.buscar_vistas` no INSTANTE DO CLAIM,
# fora de qualquer lock — violando a letra do invariante 19 ("o relatorio e
# funcao apenas da semente e do estado GRAVADO NO ENVIO") e abrindo uma
# janela onde `claim`s concorrentes do mesmo laboratorio liam a Pokedex antes
# de qualquer um escrever nela.
#
# Decisao tomada: (a) gravar o retrato da Pokedex no DESPACHO, em
# `Expedicao.especies_vistas_no_envio`, e o `claim` ler so essa coluna —
# nunca mais a Pokedex ao vivo. Prova: uma mutacao na Pokedex DEPOIS do
# despacho e ANTES do claim (o que uma DESCOBERTA concorrente de outra
# expedicao do mesmo laboratorio faria) nao pode vazar para dentro do
# relatorio desta expedicao.


def test_claim_usa_o_retrato_do_envio_e_ignora_mutacao_posterior_na_pokedex(sessao_db):
    sessao = _registrar("Achado3")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinador_pronto(sessao)

    despacho = _despachar(sessao, treinador_id, local_id=LOCAL_ROUTE_1)
    expedicao_id = uuid.UUID(despacho["id"])

    with SessionLocal() as sessao_local:
        gravado = sessao_local.get(Expedicao, expedicao_id)
        # Pidgey (16) e Rattata (19), as unicas especies de route-1, nunca
        # foram vistas por este laboratorio recem-nascido.
        assert 16 not in gravado.especies_vistas_no_envio
        assert 19 not in gravado.especies_vistas_no_envio

    # Mutacao externa DEPOIS do despacho: alguem (ou outra expedicao
    # concorrente do MESMO laboratorio) marca as duas especies como vistas.
    with SessionLocal() as sessao_local:
        sessao_local.execute(
            text(
                """
                INSERT INTO pokedex_entradas (laboratorio_id, especie_id, visto, capturado)
                VALUES (:lab, 16, true, false), (:lab, 19, true, false)
                """
            ),
            {"lab": str(laboratorio_id)},
        )
        sessao_local.commit()

    with SessionLocal() as sessao_local:
        expedicao = sessao_local.get(Expedicao, expedicao_id)
        expedicao.eta = datetime.now(UTC) - timedelta(seconds=1)
        sessao_local.commit()

    with SessionLocal() as sessao_local:
        resultado = expedicoes_service.claim(sessao_local, laboratorio_id, expedicao_id)

    avistamentos = resultado.relatorio.especies_vistas
    # route-1 sempre tem pelo menos um encontro (ENCONTROS_MINIMOS = 1).
    assert avistamentos
    # Se o `claim` tivesse lido a Pokedex ao vivo (o bug), a mutacao externa
    # faria estas especies aparecerem como ja conhecidas.
    assert all(av.primeira_vez for av in avistamentos), avistamentos
