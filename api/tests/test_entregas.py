"""Cobertura de `/deliveries` (spec 008): criterios 13 a 32, mais o que so
aparece atravessando banco, transacao e HTTP.

`game/delivery.py` ja tem a cobertura pura em `test_game_delivery.py` (a
tabela de `piso_de_raridade`, a ordem das rolagens de `gerar_pedido`, a
derivacao de `estado_observado_entrega`). Este arquivo nao repete nada disso
(Artigo IX) — o que ele cobre e o que so existe atravessando SERVICO,
TRANSACAO e HTTP.

Duas famílias de teste pedem setups diferentes:

- **Geracao** (criterios 13 a 17, 21 e 22) precisa do sorteio de verdade —
  `POST /deliveries/refresh` chamando `game.delivery.gerar_pedidos` com o
  catalogo real do laboratorio — porque e exatamente isso que se testa.
- **Aceite e conclusao** (criterios 18 a 20 e 23 a 32) nao se importam COMO o
  pedido nasceu, so com o que ele PEDE. `_criar_entrega` grava um pedido
  direto no banco, sem depender de achar uma semente com o formato certo —
  mais rapido e mais claro do que calibrar `random.Random` para um resultado
  especifico que nao e o que estes testes verificam.

O teste mais sensivel e `test_duas_conclusoes_concorrentes_da_mesma_entrega_
resolvem_uma_unica_vez`: e a PRIMEIRA operacao destrutiva do jogo (plan.md) —
resolver duas vezes apagaria Pokemon que nao deviam sair, e isso e
irreparavel. Conta linhas no banco, nunca a resposta HTTP.
"""

from __future__ import annotations

import random
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.core.database import SessionLocal, engine
from app.game import balance
from app.game import laboratorio as laboratorio_dominio
from app.game import trainers as trainers_dominio
from app.main import app
from app.models import (
    Entrega,
    EntregaRequisito,
    Expedicao,
    Laboratorio,
    Local,
    LocalDesbloqueado,
    PokemonInstancia,
    Treinador,
)
from app.repositories import entregas as entregas_repo
from app.services import entregas as entregas_service
from app.services import expedicoes as expedicoes_service
from tests.conftest import requer_banco

pytestmark = requer_banco

client = TestClient(app)

PIDGEY_ID = 16
RATTATA_ID = 19

# A captura que ENCHE a bagagem (criterio 31, tarefa 3): time de TRES
# starters (capacidade_bagagem(3) = CAPACIDADE_TOTAL_TREINADOR - 3 = 3), Route
# 1, 10 poke-balls. Achada rodando o despacho de verdade com este time contra
# varias sementes e procurando o evento `BAGAGEM_CHEIA` na saida — a mesma
# tecnica de `test_relatorio.SEMENTE_SUCESSO_RICA`.
SEMENTE_BAGAGEM_CHEIA = 5

# O "PRIMEIRO dos tres pedidos sorteados", usada so pelos testes de GERACAO
# (13 a 17) e de REPOSICAO (21 e 22), que precisam do sorteio de verdade.
SEMENTE_GERACAO = 2


# --- Apoio -------------------------------------------------------------------


def _registrar(usuario: str) -> dict:
    resposta = client.post("/auth/register", json={"usuario": usuario, "senha": f"{usuario}12345"})
    assert resposta.status_code == 201
    return resposta.json()


def _cabecalho(sessao: dict) -> dict:
    return {"Authorization": f"Bearer {sessao['token']}"}


def _treinadores(sessao: dict) -> list[dict]:
    resposta = client.get("/trainers", headers=_cabecalho(sessao))
    assert resposta.status_code == 200
    return resposta.json()["items"]


def _ficha_treinador(sessao: dict, treinador_id: str) -> dict:
    resposta = client.get(f"/trainers/{treinador_id}", headers=_cabecalho(sessao))
    assert resposta.status_code == 200
    return resposta.json()


def _pokemon_livres(sessao: dict) -> list[dict]:
    resposta = client.get("/pokemon", params={"livre": True}, headers=_cabecalho(sessao))
    assert resposta.status_code == 200
    return resposta.json()["items"]


def _definir_time(sessao: dict, treinador_id: str, pokemon_ids: list[str]):
    return client.put(
        f"/trainers/{treinador_id}/team",
        json={"pokemon_ids": pokemon_ids},
        headers=_cabecalho(sessao),
    )


def _despachar(sessao: dict, treinador_id: str, local_id: str = "route-1", carga=None):
    return client.post(
        "/expeditions",
        json={"treinador_id": treinador_id, "local_id": local_id, "carga": carga or []},
        headers=_cabecalho(sessao),
    )


def _claim_expedicao(sessao: dict, expedicao_id: str):
    return client.post(f"/expeditions/{expedicao_id}/claim", headers=_cabecalho(sessao))


def _perfil(sessao: dict) -> dict:
    resposta = client.get("/me", headers=_cabecalho(sessao))
    assert resposta.status_code == 200
    return resposta.json()


def _listar_entregas(sessao: dict):
    return client.get("/deliveries", headers=_cabecalho(sessao))


def _refresh_entregas(sessao: dict):
    return client.post("/deliveries/refresh", headers=_cabecalho(sessao))


def _aceitar_entrega(sessao: dict, entrega_id, treinador_id: str, pokemon_ids: list[str]):
    return client.post(
        f"/deliveries/{entrega_id}/accept",
        json={"treinador_id": treinador_id, "pokemon_ids": pokemon_ids},
        headers=_cabecalho(sessao),
    )


def _claim_entrega(sessao: dict, entrega_id):
    return client.post(f"/deliveries/{entrega_id}/claim", headers=_cabecalho(sessao))


def _soltar(sessao: dict, pokemon_id: str):
    return client.delete(f"/pokemon/{pokemon_id}", headers=_cabecalho(sessao))


def _fixar_semente_expedicao(monkeypatch, semente: int) -> None:
    monkeypatch.setattr(expedicoes_service.random, "randrange", lambda *_args, s=semente: s)


def _fixar_gerador_de_entregas(monkeypatch, semente: int) -> None:
    """`entregas_service.random` E o modulo `random`: capturar a classe
    original antes de substituir, ou a lambda chamaria a si mesma."""
    classe_original = random.Random
    monkeypatch.setattr(
        entregas_service.random, "Random", lambda *_a, **_k: classe_original(semente)
    )


def _inserir_pokemon_no_viveiro(
    sessao_db, laboratorio_id: uuid.UUID, especie_id: int, *, nivel: int = 3, quantidade: int = 1
) -> list[uuid.UUID]:
    """Insere Pokemon direto no banco, sem passar pela captura (apoio de teste)."""
    agora = datetime.now(UTC)
    ids: list[uuid.UUID] = []
    for _ in range(quantidade):
        pokemon_id = uuid.uuid4()
        sessao_db.add(
            PokemonInstancia(
                id=pokemon_id,
                laboratorio_id=laboratorio_id,
                especie_id=especie_id,
                nivel=nivel,
                experiencia=0,
                hp_atual_pct=100,
                hp_atualizado_em=agora,
                treinador_id=None,
                origem="CAPTURADO",
                local_captura_id=None,
                capturado_em=agora,
            )
        )
        ids.append(pokemon_id)
    sessao_db.commit()
    return ids


def _criar_entrega(
    sessao_db,
    laboratorio_id: uuid.UUID,
    *,
    requisitos: dict[int, int],
    destino_id: str = "pallet-town",
    expira_em: datetime | None = None,
) -> uuid.UUID:
    """Grava um pedido direto no banco, sem passar por `game.delivery.gerar_pedidos`.

    Apoio de teste: o aceite e a conclusao (criterios 18 a 20 e 23 a 32) nao
    se importam COMO o pedido nasceu, so com o que ele PEDE. Ver o docstring
    do modulo.
    """
    agora = datetime.now(UTC)
    entrega_id = uuid.uuid4()
    sessao_db.add(
        Entrega(
            id=entrega_id,
            laboratorio_id=laboratorio_id,
            titulo="Encomenda de teste para Pallet Town",
            local_destino_id=destino_id,
            status="DISPONIVEL",
            gerada_em=agora,
            expira_em=expira_em or (agora + timedelta(hours=2)),
        )
    )
    for especie_id, quantidade in requisitos.items():
        sessao_db.add(
            EntregaRequisito(entrega_id=entrega_id, especie_id=especie_id, quantidade=quantidade)
        )
    sessao_db.commit()
    return entrega_id


def _expirar_entrega(sessao_db, entrega_id) -> None:
    sessao_db.expire_all()
    entrega = sessao_db.get(
        Entrega, entrega_id if isinstance(entrega_id, uuid.UUID) else uuid.UUID(entrega_id)
    )
    entrega.expira_em = datetime.now(UTC) - timedelta(seconds=1)
    sessao_db.commit()


def _forjar_eta_passado_entrega(sessao_db, entrega_id) -> None:
    sessao_db.expire_all()
    entrega = sessao_db.get(
        Entrega, entrega_id if isinstance(entrega_id, uuid.UUID) else uuid.UUID(entrega_id)
    )
    entrega.eta = datetime.now(UTC) - timedelta(seconds=1)
    sessao_db.commit()


def _forjar_sorteio_antigo(sessao_db, laboratorio_id: uuid.UUID) -> None:
    """Carimba `entregas_geradas_em` no passado distante, para que
    `segundos_para_regerar` ja seja zero sem esperar os 15 minutos de verdade."""
    sessao_db.expire_all()
    laboratorio = sessao_db.get(Laboratorio, laboratorio_id)
    laboratorio.entregas_geradas_em = datetime.now(UTC) - timedelta(
        minutes=balance.INTERVALO_REGERAR_ENTREGAS_MINUTOS + 5
    )
    sessao_db.commit()


def _status_gravado_da_entrega(sessao_db, entrega_id) -> str:
    sessao_db.expire_all()
    return sessao_db.scalar(
        select(Entrega.status).where(
            Entrega.id
            == (entrega_id if isinstance(entrega_id, uuid.UUID) else uuid.UUID(entrega_id))
        )
    )


def _contar_pokemon_existentes(sessao_db, pokemon_ids) -> int:
    sessao_db.expire_all()
    ids = [pid if isinstance(pid, uuid.UUID) else uuid.UUID(pid) for pid in pokemon_ids]
    return (
        sessao_db.scalar(
            select(func.count()).select_from(PokemonInstancia).where(PokemonInstancia.id.in_(ids))
        )
        or 0
    )


@contextmanager
def _contar_consultas():
    contagem = {"total": 0}

    def _ouvir(conn, cursor, statement, parameters, context, executemany):
        contagem["total"] += 1

    event.listen(engine, "before_cursor_execute", _ouvir)
    try:
        yield contagem
    finally:
        event.remove(engine, "before_cursor_execute", _ouvir)


def _retrato(sessao_db, *, laboratorio_id: uuid.UUID, treinador_id: uuid.UUID, entrega_id):
    """Um retrato comparavel do laboratorio, para o teste de segunda chamada
    (mesmo raciocinio de `test_relatorio._retrato`)."""
    sessao_db.commit()
    sessao_db.expire_all()
    laboratorio = sessao_db.get(Laboratorio, laboratorio_id)
    treinador = sessao_db.get(Treinador, treinador_id)
    entrega = sessao_db.get(
        Entrega, entrega_id if isinstance(entrega_id, uuid.UUID) else uuid.UUID(entrega_id)
    )
    pokemon_ids_restantes = sorted(
        str(p.id)
        for p in sessao_db.scalars(
            select(PokemonInstancia).where(PokemonInstancia.laboratorio_id == laboratorio_id)
        )
    )
    return {
        "laboratorio": (laboratorio.nivel, laboratorio.experiencia, laboratorio.moedas),
        "treinador": (
            treinador.nivel,
            treinador.experiencia,
            treinador.status,
            treinador.entregas_concluidas,
        ),
        "entrega": (entrega.status, entrega.resultado_resumo),
        "pokemon_ids": pokemon_ids_restantes,
    }


# --- Criterio 13 ---------------------------------------------------------------
# Pokedex vazia: a Central gera pedidos normalmente.


def test_pokedex_vazia_gera_pedidos_normalmente(sessao_db):
    sessao = _registrar("Criterio13PokedexVazia")
    pokedex = client.get("/pokedex", headers=_cabecalho(sessao)).json()
    # Um laboratorio recem-criado e o unico jeito de ter a Pokedex "vazia" no
    # sentido do criterio: nada alem dos tres iniciais, que o kit inicial ja
    # marca vistos e capturados (regra 9 da spec 008: a Pokedex nao participa
    # da geracao de pedidos, entao nao importa o que ela contem).
    assert pokedex["capturadas"] == len(balance.STARTER_SPECIES_IDS)

    resposta = _refresh_entregas(sessao)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo["items"]) == balance.ENTREGAS_DISPONIVEIS
    for entrega in corpo["items"]:
        assert 1 <= len(entrega["requisitos"]) <= balance.ESPECIES_MAXIMAS_POR_ENTREGA


# --- Criterio 14 -----------------------------------------------------------------
# Laboratorio nivel 1: nenhuma especie pedida esta fora da banda comum.


def test_laboratorio_nivel_1_nao_pede_especie_fora_da_banda_comum(sessao_db, monkeypatch):
    sessao = _registrar("Criterio14BandaComum")
    _fixar_gerador_de_entregas(monkeypatch, SEMENTE_GERACAO)

    corpo = _refresh_entregas(sessao).json()

    especies_pedidas = {
        requisito["especie_id"] for item in corpo["items"] for requisito in item["requisitos"]
    }
    # So Pidgey e Rattata vivem em Pallet Town/Route 1, as unicas alcancaveis
    # para um laboratorio nivel 1 recem-criado.
    assert especies_pedidas <= {PIDGEY_ID, RATTATA_ID}
    assert especies_pedidas  # gerou pelo menos um pedido com conteudo


# --- Criterio 15 -----------------------------------------------------------------
# Laboratorio de nivel alto: a banda inclui especies raras.


def test_laboratorio_de_nivel_alto_a_banda_inclui_especies_raras(sessao_db, monkeypatch):
    sessao = _registrar("Criterio15BandaRara")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    laboratorio = sessao_db.get(Laboratorio, laboratorio_id)
    laboratorio.nivel = balance.NIVEL_LABORATORIO_BANDA_TOTAL

    # Marca "route-2" visitado direto no banco (apoio de teste, sem rodar a
    # cadeia de quatro expedicoes que desbloquearia o caminho de verdade): o
    # alcance so precisa de um VIZINHO visitado, e isso basta para abrir
    # Viridian City e Viridian Forest, onde vivem Metapod e Kakuna (taxa 120 —
    # mais raros que os 255 de Pidgey e Rattata, as unicas especies que Pallet
    # Town e Route 1 sozinhas alcancam).
    sessao_db.add(LocalDesbloqueado(laboratorio_id=laboratorio_id, local_id="route-2"))
    sessao_db.commit()

    _fixar_gerador_de_entregas(monkeypatch, 0)
    corpo = _refresh_entregas(sessao).json()

    especies_pedidas = {
        requisito["especie_id"] for item in corpo["items"] for requisito in item["requisitos"]
    }
    assert especies_pedidas - {PIDGEY_ID, RATTATA_ID}  # algo alem da banda comum apareceu


# --- Criterio 16 -----------------------------------------------------------------
# Toda especie pedida vive em algum local alcancavel.


def test_toda_especie_pedida_vive_em_local_alcancavel(sessao_db):
    sessao = _registrar("Criterio16Alcancavel")

    corpo = _refresh_entregas(sessao).json()

    especies_em_local_alcancavel = {PIDGEY_ID, RATTATA_ID}  # as duas unicas que vivem ali
    for item in corpo["items"]:
        for requisito in item["requisitos"]:
            assert requisito["especie_id"] in especies_em_local_alcancavel


# --- Regra 15 e invariante 16 ----------------------------------------------------
# O destino e sempre uma CIDADE, e sempre uma ja desbloqueada.
#
# A revisao por mutacao pegou este buraco: `test_game_delivery.py::
# test_o_destino_e_uma_cidade_desbloqueada` recebe `cidades=(VIRIDIAN,)` ja
# filtrada e confirma que o destino e Viridian — tautologia. O filtro de
# verdade mora em `services/entregas._cidades_desbloqueadas`, e as duas
# metades dele (`tipo == CIDADE` e `in visitados`) puderam ser removidas,
# uma de cada vez, com os 1242 testes verdes.
#
# Estes dois leem o MAPA DO BANCO para montar o esperado, em vez de repetir a
# condicao do codigo — repetir a condicao seria a mesma tautologia num nivel
# acima.


def test_o_destino_de_todo_pedido_e_uma_cidade(sessao_db):
    # O laboratorio novo so tem Pallet Town aberta, e Pallet E cidade — entao
    # sem desbloquear uma ROTA este teste passaria mesmo com o filtro de tipo
    # removido, porque nao haveria nao-cidade candidata. Foi exatamente assim
    # que a primeira versao dele nasceu tautologica.
    sessao = _registrar("Regra15Cidade")
    laboratorio_id = sessao["laboratorio"]["id"]

    # Um add+commit por linha: o insert em lote de chave composta tropeca na
    # sentinela do SQLAlchemy, e e assim que o resto do arquivo ja faz.
    rotas_abertas = ["route-1", "route-2"]
    for local_id in rotas_abertas:
        sessao_db.add(LocalDesbloqueado(laboratorio_id=laboratorio_id, local_id=local_id))
        sessao_db.commit()

    corpo = _refresh_entregas(sessao).json()

    for local_id in rotas_abertas:
        local = sessao_db.get(Local, local_id)
        assert local.tipo != "CIDADE", "o cenario depende destes serem rotas"

    for item in corpo["items"]:
        assert item["local_destino_id"] not in rotas_abertas


def test_o_destino_de_todo_pedido_e_uma_cidade_ja_desbloqueada(sessao_db):
    sessao = _registrar("Regra15Desbloqueada")
    laboratorio_id = sessao["laboratorio"]["id"]

    corpo = _refresh_entregas(sessao).json()

    abertos = {
        linha.local_id
        for linha in sessao_db.query(LocalDesbloqueado)
        .filter(LocalDesbloqueado.laboratorio_id == laboratorio_id)
        .all()
    }
    cidades_fechadas = {
        local.id
        for local in sessao_db.query(Local).all()
        if local.tipo == "CIDADE" and local.id not in abertos
    }
    assert cidades_fechadas, "o seed precisa ter cidade fechada para o teste valer"
    for item in corpo["items"]:
        assert item["local_destino_id"] in abertos
        assert item["local_destino_id"] not in cidades_fechadas


# --- Criterio 17 -----------------------------------------------------------------
# No maximo tres especies distintas por pedido, sem repeticao.


def test_pedido_tem_no_maximo_tres_especies_distintas(sessao_db):
    sessao = _registrar("Criterio17MaxEspecies")

    corpo = _refresh_entregas(sessao).json()

    for item in corpo["items"]:
        especies = [r["especie_id"] for r in item["requisitos"]]
        assert len(especies) <= balance.ESPECIES_MAXIMAS_POR_ENTREGA
        assert len(especies) == len(set(especies))


# --- Criterio 18 -----------------------------------------------------------------
# Prazo vencido sem aceite: o pedido deixa de ser aceitavel.


def test_pedido_vencido_deixa_de_ser_aceitavel(sessao_db):
    sessao = _registrar("Criterio18Vencido")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 1})
    _expirar_entrega(sessao_db, entrega_id)

    corpo = _listar_entregas(sessao).json()

    item = next(i for i in corpo["items"] if i["id"] == str(entrega_id))
    assert item["estado_observado"] == "EXPIRADA"
    assert item["atendivel"] is False


# --- Criterio 19 (e item extra 6: EXPIRACAO NAO ESCREVE) -----------------------
# Consultar um pedido vencido cem vezes: nenhuma escrita acontece por causa
# da expiracao.


def test_consultar_entrega_vencida_cem_vezes_nao_escreve_nada(sessao_db):
    sessao = _registrar("Criterio19NaoEscreve")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 1})
    _expirar_entrega(sessao_db, entrega_id)

    for _ in range(100):
        corpo = _listar_entregas(sessao).json()
        item = next(i for i in corpo["items"] if i["id"] == str(entrega_id))
        assert item["estado_observado"] == "EXPIRADA"

    assert _status_gravado_da_entrega(sessao_db, entrega_id) == "DISPONIVEL"


# --- Criterio 20 -----------------------------------------------------------------
# Pedido expirado: aceitar e recusado.


def test_aceitar_pedido_expirado_e_recusado(sessao_db):
    sessao = _registrar("Criterio20AceitarVencido")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinadores(sessao)[0]["id"]
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 1})
    pidgey_ids = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=1)
    _expirar_entrega(sessao_db, entrega_id)

    resposta = _aceitar_entrega(sessao, entrega_id, treinador_id, [str(pidgey_ids[0])])

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "ENTREGA_EXPIRADA"


# --- Criterio 21 (e item extra 7, metade "repor nao espera") -------------------
# Vaga aberta por expiracao: repor nao tem espera, mesmo logo apos um
# descarte que acabou de consumir o intervalo.


def test_vaga_aberta_por_expiracao_e_reposta_sem_espera(sessao_db):
    sessao = _registrar("Criterio21RepoeSemEsperar")

    assert _refresh_entregas(sessao).status_code == 200  # preenche a lista pela 1a vez
    descarte = _refresh_entregas(sessao)  # lista cheia e valida: descarta e regenera
    assert descarte.status_code == 200

    # `items` acumula o HISTORICO inteiro (inclusive o que o descarte acima
    # acabou de marcar DESCARTADA); e preciso achar uma das tres DISPONIVEL
    # de verdade, nao confiar na posicao.
    entrega_a_expirar = next(
        item for item in descarte.json()["items"] if item["estado_observado"] == "DISPONIVEL"
    )
    _expirar_entrega(sessao_db, entrega_a_expirar["id"])

    resposta = _refresh_entregas(sessao)

    assert resposta.status_code == 200  # nenhuma espera, mesmo com o sorteio recem-carimbado
    corpo = resposta.json()
    # `items` acumula o historico (inclusive os tres descartados na rodada
    # anterior); o que importa e que a lista VALIDA voltou a ter tres.
    validos = [i for i in corpo["items"] if i["estado_observado"] == "DISPONIVEL"]
    assert len(validos) == balance.ENTREGAS_DISPONIVEIS


# --- Item extra 16 (revisao da Fase 8): REPOR NAO LIBERA UMA REGERACAO --------
# GRATUITA. Forca o carimbo do ultimo sorteio para o passado (como se o
# intervalo ja tivesse passado ha muito), repoe UMA vaga por expiracao, e
# confere que a lista (agora cheia de novo, com a vaga reposta) ainda EXIGE
# o intervalo para ser descartada por inteiro — a reposicao tem que ter
# avancado o relogio, senao o carimbo antigo destrava um descarte gratuito.


def test_repor_vaga_nao_destrava_descarte_gratuito_da_lista_cheia(sessao_db):
    sessao = _registrar("Extra16RepoeNaoLiberaDescarte")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])

    assert _refresh_entregas(sessao).status_code == 200  # preenche (bootstrap, sem carimbo)
    cheia = _refresh_entregas(sessao)  # lista cheia e valida: descarta e carimba AGORA
    assert cheia.status_code == 200

    # Forca o carimbo para o passado distante, como se o intervalo de 15
    # minutos ja tivesse passado desde aquele descarte.
    _forjar_sorteio_antigo(sessao_db, laboratorio_id)

    entrega_a_expirar = next(
        item for item in cheia.json()["items"] if item["estado_observado"] == "DISPONIVEL"
    )
    _expirar_entrega(sessao_db, entrega_a_expirar["id"])

    reposicao = _refresh_entregas(sessao)
    assert reposicao.status_code == 200  # repor continua SEM espera (invariante 18)
    validos = [i for i in reposicao.json()["items"] if i["estado_observado"] == "DISPONIVEL"]
    assert len(validos) == balance.ENTREGAS_DISPONIVEIS

    # A lista esta cheia de novo (dois originais + o reposto agora mesmo).
    # Sem o carimbo da reposicao, o relogio antigo (ja vencido) deixaria
    # descartar a lista inteira de graca aqui. Com o carimbo, o intervalo
    # cheio volta a valer a partir da reposicao.
    descarte_apos_repor = _refresh_entregas(sessao)
    assert descarte_apos_repor.status_code == 409
    corpo = descarte_apos_repor.json()
    assert corpo["erro"]["codigo"] == "AGUARDE_PARA_REGERAR"
    segundos = corpo["erro"]["detalhes"]["segundos_para_regerar"]
    assert 0 < segundos <= balance.INTERVALO_REGERAR_ENTREGAS_MINUTOS * 60


# --- Criterio 22 (e item extra 7, metade "descartar espera") -------------------
# Regerar a lista valida antes do intervalo: recusado dizendo quanto falta.


def test_regerar_lista_valida_antes_do_intervalo_e_recusado_dizendo_quanto_falta(sessao_db):
    sessao = _registrar("Criterio22AguardeRegerar")

    assert _refresh_entregas(sessao).status_code == 200  # preenche
    assert _refresh_entregas(sessao).status_code == 200  # descarta a valida e regenera -> carimba

    resposta = _refresh_entregas(sessao)  # lista ainda valida, intervalo mal comecou

    assert resposta.status_code == 409
    corpo = resposta.json()
    assert corpo["erro"]["codigo"] == "AGUARDE_PARA_REGERAR"
    segundos = corpo["erro"]["detalhes"]["segundos_para_regerar"]
    assert 0 < segundos <= balance.INTERVALO_REGERAR_ENTREGAS_MINUTOS * 60


# --- Criterio 23 -----------------------------------------------------------------
# Pedido de dois Pidgey com quatro no viveiro: so os dois escolhidos ficam
# comprometidos.


def test_aceitar_dois_de_quatro_pidgey_compromete_so_esses_dois(sessao_db):
    sessao = _registrar("Criterio23EscolhaDoProfessor")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinadores(sessao)[0]["id"]
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 2})
    quatro_pidgey = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=4)
    escolhidos, sobrando = quatro_pidgey[:2], quatro_pidgey[2:]

    resposta = _aceitar_entrega(sessao, entrega_id, treinador_id, [str(p) for p in escolhidos])

    assert resposta.status_code == 200
    sessao_db.expire_all()
    for pokemon_id in escolhidos:
        pokemon = sessao_db.get(PokemonInstancia, pokemon_id)
        assert pokemon.comprometido_entrega_id == entrega_id
    for pokemon_id in sobrando:
        pokemon = sessao_db.get(PokemonInstancia, pokemon_id)
        assert pokemon.comprometido_entrega_id is None


# --- Criterio 24 -----------------------------------------------------------------
# Pedido de dois Pidgey: aceitar com um Pidgey e um Rattata e recusado.


def test_aceitar_com_especie_errada_e_recusado(sessao_db):
    sessao = _registrar("Criterio24EspecieErrada")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinadores(sessao)[0]["id"]
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 2})
    pidgey = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=1)
    rattata = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, RATTATA_ID, quantidade=1)

    resposta = _aceitar_entrega(sessao, entrega_id, treinador_id, [str(pidgey[0]), str(rattata[0])])

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "POKEMON_NAO_ATENDE_AO_PEDIDO"
    sessao_db.expire_all()
    assert sessao_db.get(PokemonInstancia, pidgey[0]).comprometido_entrega_id is None
    assert sessao_db.get(PokemonInstancia, rattata[0]).comprometido_entrega_id is None


# --- Criterio 25 (e item extra 11: COMPROMETIDO E INTOCAVEL) -------------------
# Pokemon comprometido: nao entra em time (e, por decorrencia, nao entra em
# expedicao, que exige time) nem em outra entrega. A recusa de solta-lo ja
# esta coberta em `test_viveiro.py::test_soltar_pokemon_comprometido_...`.


def test_pokemon_comprometido_nao_entra_em_time_nem_em_outra_entrega(sessao_db):
    sessao = _registrar("Criterio25Comprometido")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_a, treinador_b = _treinadores(sessao)[:2]
    entrega_a = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 1})
    entrega_b = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 1})
    pidgey = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=1)[0]
    assert _aceitar_entrega(sessao, entrega_a, treinador_a["id"], [str(pidgey)]).status_code == 200

    time_resposta = _definir_time(sessao, treinador_b["id"], [str(pidgey)])
    assert time_resposta.status_code == 409
    assert time_resposta.json()["erro"]["codigo"] == "POKEMON_COMPROMETIDO"

    outra_entrega = _aceitar_entrega(sessao, entrega_b, treinador_b["id"], [str(pidgey)])
    assert outra_entrega.status_code == 409
    assert outra_entrega.json()["erro"]["codigo"] == "POKEMON_INDISPONIVEL"


# --- Item extra 5: ULTIMO_POKEMON tambem no aceite -----------------------------


def test_aceitar_entrega_que_esvaziaria_o_laboratorio_e_recusado(sessao_db):
    sessao = _registrar("Extra5UltimoPokemonAceite")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinadores(sessao)[0]["id"]
    livres = _pokemon_livres(sessao)
    # Esvazia os tres iniciais, um de cada vez (o ultimo so sai substituido
    # pelos dois Pidgey inseridos a seguir).
    assert (
        client.delete(f"/pokemon/{livres[0]['id']}", headers=_cabecalho(sessao)).status_code == 204
    )
    assert (
        client.delete(f"/pokemon/{livres[1]['id']}", headers=_cabecalho(sessao)).status_code == 204
    )
    pidgey_ids = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=2)
    assert (
        client.delete(f"/pokemon/{livres[2]['id']}", headers=_cabecalho(sessao)).status_code == 204
    )
    # Agora o laboratorio tem SO os dois Pidgey.
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 2})

    resposta = _aceitar_entrega(sessao, entrega_id, treinador_id, [str(p) for p in pidgey_ids])

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "ULTIMO_POKEMON"
    sessao_db.expire_all()
    assert (
        sessao_db.scalar(
            select(func.count())
            .select_from(PokemonInstancia)
            .where(PokemonInstancia.laboratorio_id == laboratorio_id)
        )
        == 2
    )


# --- Item CRITICO da revisao da Fase 8: duas entregas aceitas NUNCA podem ------
# zerar o laboratorio juntas, e a soltura tem de enxergar quem ja esta
# prometido a OUTRA entrega. Reproduz os dois roteiros do revisor (que
# zeraram o banco contra o compose) direto contra o service, contando linhas
# no banco em cada passo.


def test_duas_entregas_aceitas_juntas_nao_podem_esvaziar_o_laboratorio(sessao_db):
    sessao = _registrar("CriticoDuasEntregasNaoZeram")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_a, treinador_b = _treinadores(sessao)[:2]
    bulbasaur_id, charmander_id, squirtle_id = balance.STARTER_SPECIES_IDS
    livres = {p["especie_id"]: p["id"] for p in _pokemon_livres(sessao)}
    assert len(livres) == 3  # os tres iniciais, nenhum comprometido ainda

    entrega_a = _criar_entrega(sessao_db, laboratorio_id, requisitos={bulbasaur_id: 1})
    entrega_b = _criar_entrega(
        sessao_db, laboratorio_id, requisitos={charmander_id: 1, squirtle_id: 1}
    )

    aceite_a = _aceitar_entrega(sessao, entrega_a, treinador_a["id"], [livres[bulbasaur_id]])
    assert aceite_a.status_code == 200

    # Sozinha, entrega_b levaria os outros DOIS iniciais — e zeraria o
    # laboratorio junto com o Bulbasaur ja comprometido para entrega_a. Tem
    # de ser recusada.
    aceite_b = _aceitar_entrega(
        sessao, entrega_b, treinador_b["id"], [livres[charmander_id], livres[squirtle_id]]
    )
    assert aceite_b.status_code == 409
    assert aceite_b.json()["erro"]["codigo"] == "ULTIMO_POKEMON"

    sessao_db.expire_all()
    total_no_banco = sessao_db.scalar(
        select(func.count())
        .select_from(PokemonInstancia)
        .where(PokemonInstancia.laboratorio_id == laboratorio_id)
    )
    assert total_no_banco == 3  # nada foi removido pela recusa
    assert (
        sessao_db.get(PokemonInstancia, uuid.UUID(livres[charmander_id])).comprometido_entrega_id
        is None
    )


def test_soltar_nao_pode_remover_o_ultimo_pokemon_livre_quando_outro_esta_comprometido(sessao_db):
    sessao = _registrar("CriticoSoltarRespeitaComprometido")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinadores(sessao)[0]["id"]
    livres_iniciais = _pokemon_livres(sessao)
    pidgey_id = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=1)[0]
    # Quatro Pokemon no total: os tres iniciais, livres, mais um Pidgey.
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 1})
    assert _aceitar_entrega(sessao, entrega_id, treinador_id, [str(pidgey_id)]).status_code == 200

    def _total_no_banco() -> int:
        sessao_db.expire_all()
        return sessao_db.scalar(
            select(func.count())
            .select_from(PokemonInstancia)
            .where(PokemonInstancia.laboratorio_id == laboratorio_id)
        )

    assert _total_no_banco() == 4  # o Pidgey comprometido ainda existe fisicamente

    # Os dois primeiros dos tres iniciais saem sem problema: ainda sobra 1
    # livre, alem do Pidgey comprometido (que vai embora so na conclusao).
    assert _soltar(sessao, livres_iniciais[0]["id"]).status_code == 204
    assert _total_no_banco() == 3
    assert _soltar(sessao, livres_iniciais[1]["id"]).status_code == 204
    assert _total_no_banco() == 2

    # O TERCEIRO (o ultimo LIVRE) tem de ser recusado: o Pidgey comprometido
    # nao conta como "fica", porque ele ja saiu por outra porta (a entrega).
    # Antes da correcao do achado critico, esta soltura passava e o
    # laboratorio chegava a zero Pokemon assim que a entrega fosse concluida.
    ultima_solta = _soltar(sessao, livres_iniciais[2]["id"])
    assert ultima_solta.status_code == 409
    assert ultima_solta.json()["erro"]["codigo"] == "ULTIMO_POKEMON"
    assert _total_no_banco() == 2  # nada foi removido pela recusa

    # E a conclusao da entrega nao some com o ultimo Pokemon que restou.
    _forjar_eta_passado_entrega(sessao_db, entrega_id)
    assert _claim_entrega(sessao, entrega_id).status_code == 200
    assert _total_no_banco() == 1  # o livre sobrevivente, nunca zero


# --- Item extra 15 (revisao da Fase 8): ATENDIVEL NAO PROMETE O QUE O -----------
# ACEITE RECUSA. Mesmo cenario do teste acima (so dois Pidgey no laboratorio,
# entrega pede os dois), mas verificando a FICHA que `GET /deliveries`
# mostra ANTES de tentar aceitar.


def test_atendivel_e_falso_quando_o_aceite_esvaziaria_o_laboratorio(sessao_db):
    sessao = _registrar("Extra15AtendivelUltimoPokemon")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    livres = _pokemon_livres(sessao)
    assert (
        client.delete(f"/pokemon/{livres[0]['id']}", headers=_cabecalho(sessao)).status_code == 204
    )
    assert (
        client.delete(f"/pokemon/{livres[1]['id']}", headers=_cabecalho(sessao)).status_code == 204
    )
    _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=2)
    assert (
        client.delete(f"/pokemon/{livres[2]['id']}", headers=_cabecalho(sessao)).status_code == 204
    )
    # Agora o laboratorio tem SO os dois Pidgey: mandar os dois pelo pedido
    # esvaziaria o acervo (invariante 25), exatamente o que o aceite recusa.
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 2})

    corpo = _listar_entregas(sessao).json()

    item = next(i for i in corpo["items"] if i["id"] == str(entrega_id))
    assert item["atendivel"] is False
    assert item["motivo"] is not None


# --- Criterio 26 -----------------------------------------------------------------
# Entrega aceita: o treinador fica indisponivel ate a conclusao.


def test_entrega_aceita_deixa_treinador_indisponivel_ate_a_conclusao(sessao_db):
    sessao = _registrar("Criterio26TreinadorOcupado")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinadores(sessao)[0]["id"]
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 1})
    pidgey = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=1)

    aceite = _aceitar_entrega(sessao, entrega_id, treinador_id, [str(pidgey[0])])
    assert aceite.status_code == 200
    assert _ficha_treinador(sessao, treinador_id)["status"] == "EM_ENTREGA"

    _forjar_eta_passado_entrega(sessao_db, entrega_id)
    conclusao = _claim_entrega(sessao, entrega_id)
    assert conclusao.status_code == 200
    assert _ficha_treinador(sessao, treinador_id)["status"] == "DISPONIVEL"


# --- Criterio 27 -----------------------------------------------------------------
# Entrega concluida: os Pokemon entregues nao existem mais e o saldo subiu.


def test_entrega_concluida_remove_pokemon_e_credita_moedas(sessao_db):
    sessao = _registrar("Criterio27Conclusao")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinadores(sessao)[0]["id"]
    nivel_pidgey = 3
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 1})
    pidgey = _inserir_pokemon_no_viveiro(
        sessao_db, laboratorio_id, PIDGEY_ID, nivel=nivel_pidgey, quantidade=1
    )[0]
    assert _aceitar_entrega(sessao, entrega_id, treinador_id, [str(pidgey)]).status_code == 200
    moedas_antes = _perfil(sessao)["laboratorio"]["moedas"]

    _forjar_eta_passado_entrega(sessao_db, entrega_id)
    resposta = _claim_entrega(sessao, entrega_id)

    assert resposta.status_code == 200
    assert client.get(f"/pokemon/{pidgey}", headers=_cabecalho(sessao)).status_code == 404
    # Destino e Pallet Town, o proprio laboratorio: custo de viagem zero, e a
    # formula da secao 4.9 do SDD fica so a parcela por nivel.
    moedas_esperadas = balance.MOEDA_BASE + nivel_pidgey * balance.MOEDA_POR_NIVEL
    assert _perfil(sessao)["laboratorio"]["moedas"] == moedas_antes + moedas_esperadas


# --- Item CRITICO da revisao da Fase 8 (mutacao sobreviveu VERDE) --------------
# A regra 24 credita moeda E experiencia. A moeda ja tinha teste; as duas
# experiencias (laboratorio e treinador), nao. O defeito e pior que falta de
# cobertura: `resultado_resumo` grava o valor ANUNCIADO pela propria conclusao,
# e comparar resumo contra resumo nao prova nada (foi a causa de doze buracos
# na Fase 7) — por isso este teste RELE A LINHA DO BANCO e confronta com um
# valor ESPERADO, calculado da formula da secao 4.9 do SDD.


def test_entrega_concluida_credita_experiencia_do_laboratorio_e_do_treinador(sessao_db):
    sessao = _registrar("CriticoExperienciaCreditada")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = uuid.UUID(_treinadores(sessao)[0]["id"])
    total_pedido = 2
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: total_pedido})
    pidgey_ids = _inserir_pokemon_no_viveiro(
        sessao_db, laboratorio_id, PIDGEY_ID, quantidade=total_pedido
    )
    assert (
        _aceitar_entrega(
            sessao, entrega_id, str(treinador_id), [str(p) for p in pidgey_ids]
        ).status_code
        == 200
    )

    sessao_db.expire_all()
    exp_laboratorio_antes = sessao_db.get(Laboratorio, laboratorio_id).experiencia
    exp_treinador_antes = sessao_db.get(Treinador, treinador_id).experiencia

    _forjar_eta_passado_entrega(sessao_db, entrega_id)
    assert _claim_entrega(sessao, entrega_id).status_code == 200

    # A LINHA DO BANCO, nunca o `resultado_resumo` que a propria conclusao
    # acabou de gravar.
    sessao_db.expire_all()
    laboratorio = sessao_db.get(Laboratorio, laboratorio_id)
    treinador = sessao_db.get(Treinador, treinador_id)

    exp_laboratorio_esperada = exp_laboratorio_antes + balance.EXP_LAB_POR_ENTREGA * total_pedido
    exp_treinador_esperada = exp_treinador_antes + balance.EXP_TREINADOR_POR_ENTREGA

    assert laboratorio.experiencia == exp_laboratorio_esperada
    assert laboratorio.nivel == laboratorio_dominio.nivel_para_experiencia(exp_laboratorio_esperada)
    assert treinador.experiencia == exp_treinador_esperada
    assert treinador.nivel == trainers_dominio.nivel_para_experiencia(exp_treinador_esperada)


# --- Criterio 28 -----------------------------------------------------------------
# Entrega concluida: os lugares do viveiro sao devolvidos.


def test_entrega_concluida_devolve_lugares_no_viveiro(sessao_db):
    sessao = _registrar("Criterio28LugaresDevolvidos")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinadores(sessao)[0]["id"]
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 2})
    pidgey_ids = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=2)
    assert (
        _aceitar_entrega(sessao, entrega_id, treinador_id, [str(p) for p in pidgey_ids]).status_code
        == 200
    )
    ocupacao_antes = client.get("/ranch", headers=_cabecalho(sessao)).json()["ocupacao"]

    _forjar_eta_passado_entrega(sessao_db, entrega_id)
    assert _claim_entrega(sessao, entrega_id).status_code == 200

    ocupacao_depois = client.get("/ranch", headers=_cabecalho(sessao)).json()["ocupacao"]
    assert ocupacao_depois == ocupacao_antes - len(pidgey_ids)


# --- Criterio 29 (e item extra 8: CLAIM DESTRUTIVO SOB CONCORRENCIA) -----------
# Duas conclusoes concorrentes da mesma entrega: so uma resolve.


def test_duas_conclusoes_concorrentes_da_mesma_entrega_resolvem_uma_unica_vez(
    sessao_db, monkeypatch
):
    """A janela e deterministica, nao de escalonamento (achado da revisao da
    Fase 8: com so um `threading.Barrier` ANTES de chamar `claim`, o teste
    passava 23/23 quando rodado junto com o arquivo e falhava so isolado —
    sincronizar o INICIO das duas threads nao garante que as duas cheguem
    juntas na operacao que importa, que e a tentativa de travar a linha).

    Aqui o ponto de sincronizacao e `entregas_repo.travar_para_resolver`, a
    MESMA chamada que faz `SELECT ... FOR UPDATE` tanto no codigo correto
    (primeira coisa que `claim` faz) quanto numa regressao que movesse a
    checagem de status para antes do lock (a checagem aconteceria ANTES
    deste ponto, nos dois casos com a MESMA linha ainda `EM_CURSO`, porque
    nenhuma das duas threads commitou ainda). Travando as DUAS threads bem
    aqui, e so soltando quando ambas chegaram, a corrida de verdade no
    Postgres (quem pega o lock primeiro) acontece sempre, em vez de depender
    de como o SO intercala as threads.
    """
    sessao = _registrar("Criterio29Concorrencia")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = uuid.UUID(_treinadores(sessao)[0]["id"])
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 2})
    pidgey_ids = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=2)
    assert (
        _aceitar_entrega(
            sessao, entrega_id, str(treinador_id), [str(p) for p in pidgey_ids]
        ).status_code
        == 200
    )
    _forjar_eta_passado_entrega(sessao_db, entrega_id)

    original_travar = entregas_service.entregas_repo.travar_para_resolver
    ponto_de_sincronizacao = threading.Barrier(2)
    trava_contador = threading.Lock()
    chamadas = {"total": 0}

    def _travar_sincronizado(sessao_passada, laboratorio_id_passado, entrega_id_passado):
        with trava_contador:
            chamadas["total"] += 1
            e_das_duas_primeiras = chamadas["total"] <= 2
        # So as DUAS primeiras chamadas (uma por thread) esperam uma a
        # outra. Qualquer chamada extra (ex.: a segunda metade do teste
        # fosse reexecutar `claim`) so passa direto, para nunca quebrar o
        # barrier com um terceiro `wait()`.
        if e_das_duas_primeiras:
            ponto_de_sincronizacao.wait()
        return original_travar(sessao_passada, laboratorio_id_passado, entrega_id_passado)

    monkeypatch.setattr(
        entregas_service.entregas_repo, "travar_para_resolver", _travar_sincronizado
    )

    resultados: list[str] = []
    trava = threading.Lock()

    def resolver() -> None:
        with SessionLocal() as sessao_local:
            entregas_service.claim(sessao_local, laboratorio_id, entrega_id)
            with trava:
                resultados.append("ok")

    threads = [threading.Thread(target=resolver) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # As duas chamadas devolvem 200 (a segunda releem o resultado ja
    # gravado, ADR-006) — o que importa e o EFEITO, nao a resposta HTTP.
    assert resultados == ["ok", "ok"]

    assert _contar_pokemon_existentes(sessao_db, pidgey_ids) == 0  # sumiram UMA vez
    sessao_db.expire_all()
    laboratorio = sessao_db.get(Laboratorio, laboratorio_id)
    treinador = sessao_db.get(Treinador, treinador_id)
    nivel_pidgey = 3
    moedas_esperadas = 2 * (balance.MOEDA_BASE + nivel_pidgey * balance.MOEDA_POR_NIVEL)
    assert laboratorio.moedas == moedas_esperadas  # creditado UMA vez
    assert treinador.entregas_concluidas == 1


# --- Criterio 30 (e item extra 9: SEGUNDA CHAMADA NAO MUDA NADA) ---------------
# Entrega ja concluida: pedir a conclusao de novo nao muda nada.


def test_segunda_conclusao_nao_muda_nada_no_laboratorio(sessao_db):
    sessao = _registrar("Criterio30SegundaChamada")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = uuid.UUID(_treinadores(sessao)[0]["id"])
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 1})
    pidgey = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=1)[0]
    assert _aceitar_entrega(sessao, entrega_id, str(treinador_id), [str(pidgey)]).status_code == 200
    _forjar_eta_passado_entrega(sessao_db, entrega_id)

    primeira = _claim_entrega(sessao, entrega_id)
    assert primeira.status_code == 200
    retrato_apos_primeira = _retrato(
        sessao_db, laboratorio_id=laboratorio_id, treinador_id=treinador_id, entrega_id=entrega_id
    )

    segunda = _claim_entrega(sessao, entrega_id)
    assert segunda.status_code == 200
    retrato_apos_segunda = _retrato(
        sessao_db, laboratorio_id=laboratorio_id, treinador_id=treinador_id, entrega_id=entrega_id
    )

    assert primeira.json() == segunda.json()
    assert retrato_apos_primeira == retrato_apos_segunda


# --- Item extra 14 (revisao da Fase 8): SEGUNDA CHAMADA DO CLAIM MANTEM O -----
# MESMO moedas_total, mesmo que outra entrega conclua no meio das duas
# chamadas e engorde o saldo de verdade do laboratorio.


def test_segunda_chamada_do_claim_mantem_o_mesmo_moedas_total(sessao_db):
    sessao = _registrar("Extra14MoedasTotalFixo")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_a, treinador_b = _treinadores(sessao)[:2]
    entrega_a = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 1})
    entrega_b = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 1})
    pidgey_a = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=1)[0]
    pidgey_b = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=1)[0]
    assert (
        _aceitar_entrega(sessao, entrega_a, treinador_a["id"], [str(pidgey_a)]).status_code == 200
    )
    assert (
        _aceitar_entrega(sessao, entrega_b, treinador_b["id"], [str(pidgey_b)]).status_code == 200
    )
    _forjar_eta_passado_entrega(sessao_db, entrega_a)

    primeira = _claim_entrega(sessao, entrega_a)
    assert primeira.status_code == 200

    # Outra entrega conclui NO MEIO das duas chamadas, engordando o saldo de
    # verdade do laboratorio — a segunda chamada de A nao pode enxergar isso.
    _forjar_eta_passado_entrega(sessao_db, entrega_b)
    assert _claim_entrega(sessao, entrega_b).status_code == 200

    segunda = _claim_entrega(sessao, entrega_a)
    assert segunda.status_code == 200
    assert segunda.json() == primeira.json()


# --- Item extra 10: ATOMICIDADE -------------------------------------------------
# Erro no meio da gravacao da conclusao: nada e removido, e a entrega continua
# reclamavel depois.


def test_erro_no_meio_da_conclusao_nao_deixa_nada_pela_metade(sessao_db, monkeypatch):
    sessao = _registrar("Extra10Atomicidade")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinadores(sessao)[0]["id"]
    entrega_id = _criar_entrega(sessao_db, laboratorio_id, requisitos={PIDGEY_ID: 1})
    pidgey = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=1)[0]
    assert _aceitar_entrega(sessao, entrega_id, treinador_id, [str(pidgey)]).status_code == 200
    _forjar_eta_passado_entrega(sessao_db, entrega_id)

    def _quebrar(*_args, **_kwargs):
        raise RuntimeError("falha forcada para o teste de atomicidade (Artigo VII)")

    with monkeypatch.context() as remendo:
        remendo.setattr(entregas_service.pokemon_repo, "excluir", _quebrar)
        with pytest.raises(RuntimeError):
            _claim_entrega(sessao, entrega_id)

    sessao_db.expire_all()
    assert _status_gravado_da_entrega(sessao_db, entrega_id) == "EM_CURSO"
    assert _contar_pokemon_existentes(sessao_db, [pidgey]) == 1  # ninguem foi removido
    laboratorio = sessao_db.get(Laboratorio, laboratorio_id)
    assert laboratorio.moedas == 0  # nada foi creditado

    # Reclamavel depois, sem a quebra: o claim vermelho nao corrompeu nada.
    resposta = _claim_entrega(sessao, entrega_id)
    assert resposta.status_code == 200


# --- Criterio 31 -----------------------------------------------------------------
# Bagagem cheia: ha um evento dizendo que a captura parou por falta de
# espaco.


def test_evento_de_bagagem_cheia_aparece_no_relatorio_quando_a_captura_enche_a_bagagem(
    sessao_db, monkeypatch
):
    sessao = _registrar("Criterio31BagagemCheia")
    treinador_id = _treinadores(sessao)[0]["id"]
    livres = _pokemon_livres(sessao)
    assert _definir_time(sessao, treinador_id, [p["id"] for p in livres]).status_code == 200

    _fixar_semente_expedicao(monkeypatch, SEMENTE_BAGAGEM_CHEIA)
    despacho = _despachar(sessao, treinador_id, carga=[{"item_id": "poke-ball", "quantidade": 10}])
    assert despacho.status_code == 201
    expedicao_id = despacho.json()["id"]
    sessao_db.expire_all()
    expedicao = sessao_db.get(Expedicao, uuid.UUID(expedicao_id))
    expedicao.eta = datetime.now(UTC) - timedelta(seconds=1)
    sessao_db.commit()

    relatorio = _claim_expedicao(sessao, expedicao_id).json()["relatorio"]

    eventos_de_bagagem = [e for e in relatorio["eventos"] if e["tipo"] == "BAGAGEM_CHEIA"]
    assert len(eventos_de_bagagem) == 1, relatorio  # calibrado pela SEMENTE_BAGAGEM_CHEIA
    payload = eventos_de_bagagem[0]["payload"]
    assert payload["capturas"] == payload["capacidade_bagagem"]
    assert payload["capacidade_bagagem"] == balance.CAPACIDADE_TOTAL_TREINADOR - len(livres)


# --- Item extra 17 (revisao da Fase 8): LISTAGEM SEM TETO -----------------------
# `GET /deliveries` cresceria para sempre sem um corte: cada descarte deixa um
# `DESCARTADA` permanente, cada expiracao natural deixa um `DISPONIVEL` zumbi
# (invariante 17: expiracao nunca e gravada) e cada conclusao deixa mais um
# `CONCLUIDA`. `entregas_repo.LIMITE_PADRAO` e o corte; o teste planta mais
# historico do que o teto permite e confere que a lista nunca passa dele, sem
# esconder os pedidos `DISPONIVEL` recem-gerados (os mais RECENTES, que o
# `ORDER BY gerada_em DESC` sempre traz para dentro da pagina).


def test_listagem_de_entregas_respeita_o_teto_mesmo_com_muito_historico(sessao_db):
    sessao = _registrar("Extra17ListagemRespeitaTeto")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])

    agora = datetime.now(UTC)
    historico = entregas_repo.LIMITE_PADRAO + 10
    for indice in range(historico):
        sessao_db.add(
            Entrega(
                id=uuid.uuid4(),
                laboratorio_id=laboratorio_id,
                titulo=f"Historico de teste {indice}",
                local_destino_id="pallet-town",
                status="DESCARTADA",
                gerada_em=agora - timedelta(days=1, minutes=indice),
                expira_em=agora - timedelta(days=1),
            )
        )
    sessao_db.commit()

    assert _refresh_entregas(sessao).status_code == 200  # gera os 3 pedidos validos de agora

    corpo = _listar_entregas(sessao).json()

    assert len(corpo["items"]) == entregas_repo.LIMITE_PADRAO  # nunca mais que o teto
    validos = [i for i in corpo["items"] if i["estado_observado"] == "DISPONIVEL"]
    assert len(validos) == balance.ENTREGAS_DISPONIVEIS  # os recentes nunca somem da pagina


# --- Item extra 13: N+1 ---------------------------------------------------------
# GET /deliveries emite um numero CONSTANTE de consultas, independente de
# quantos pedidos (validos, vencidos, aceitos ou descartados) existem.


def test_get_deliveries_emite_numero_constante_de_consultas(sessao_db):
    sessao_pequena = _registrar("Extra13SemHistorico")
    assert _refresh_entregas(sessao_pequena).status_code == 200  # 3 entregas, zero historico

    with _contar_consultas() as pequena:
        resposta_pequena = _listar_entregas(sessao_pequena)
    assert resposta_pequena.status_code == 200

    sessao_grande = _registrar("Extra13ComHistorico")
    laboratorio_id = uuid.UUID(sessao_grande["laboratorio"]["id"])
    assert _refresh_entregas(sessao_grande).status_code == 200
    for _ in range(5):
        _forjar_sorteio_antigo(sessao_db, laboratorio_id)
        assert _refresh_entregas(sessao_grande).status_code == 200  # descarta e regenera

    entregas_no_banco = sessao_db.scalar(
        select(func.count()).select_from(Entrega).where(Entrega.laboratorio_id == laboratorio_id)
    )
    assert entregas_no_banco > 3  # ha historico de verdade acumulado

    with _contar_consultas() as grande:
        resposta_grande = _listar_entregas(sessao_grande)
    assert resposta_grande.status_code == 200

    assert grande["total"] == pequena["total"]


# --- Escopo (criterio 32) -------------------------------------------------------
# Entrega de outro laboratorio: 404, nunca 403.


def test_entrega_de_outro_laboratorio_devolve_404(sessao_db):
    sessao_a = _registrar("Criterio32EscopoA")
    sessao_b = _registrar("Criterio32EscopoB")
    laboratorio_a = uuid.UUID(sessao_a["laboratorio"]["id"])
    entrega_de_a = _criar_entrega(sessao_db, laboratorio_a, requisitos={PIDGEY_ID: 1})
    treinador_de_b = _treinadores(sessao_b)[0]["id"]

    resposta_aceite = _aceitar_entrega(sessao_b, entrega_de_a, treinador_de_b, [])
    assert resposta_aceite.status_code == 404
    assert resposta_aceite.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"

    resposta_claim = _claim_entrega(sessao_b, entrega_de_a)
    assert resposta_claim.status_code == 404
    assert resposta_claim.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"

    lista_de_b = _listar_entregas(sessao_b).json()
    assert str(entrega_de_a) not in {item["id"] for item in lista_de_b["items"]}
