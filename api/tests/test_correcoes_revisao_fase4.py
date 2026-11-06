"""Regressao dos defeitos encontrados na revisao adversarial da Fase 4."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.database import engine
from app.game import balance, team
from app.game.power import PokemonNoTime, poder_do_time
from app.main import app

cliente = TestClient(app)


def _banco_disponivel() -> bool:
    try:
        with engine.connect():
            return True
    except OperationalError:
        return False


# --- ALTO: o bonus do treinador sumia no arredondamento ------------------
# poder_do_time devolvia inteiro, e o passo de 3% por nivel cabia inteiro
# dentro do arredondamento em times pequenos: um Bulbasaur nivel 5 dava 8 com
# treinador de nivel 1, 2 ou 3. O criterio de aceite 9 era falso na pratica.


def _bulbasaur_nivel_5() -> list[PokemonNoTime]:
    return [PokemonNoTime(nivel=5, soma_stats_base=318, hp_atual_pct=100)]


def test_niveis_de_treinador_adjacentes_nao_empatam_no_caso_mais_apertado():
    poderes = [poder_do_time(_bulbasaur_nivel_5(), nivel) for nivel in range(1, 11)]
    assert len(set(poderes)) == len(poderes), poderes


def test_poder_cresce_monotonicamente_com_o_nivel_do_treinador():
    poderes = [poder_do_time(_bulbasaur_nivel_5(), nivel) for nivel in range(1, 21)]
    assert poderes == sorted(poderes)


def test_poder_respeita_a_precisao_declarada_no_balance():
    valor = poder_do_time(_bulbasaur_nivel_5(), 7)
    assert round(valor, balance.CASAS_DECIMAIS_PODER) == valor


# --- MEDIO: leitura explodia se o time passasse do maximo ----------------
# capacidade_bagagem levantava TimeCheio, e _campos_comuns a chamava em TODA
# leitura: um time corrompido derrubava a listagem inteira com 500.


@pytest.mark.parametrize("tamanho", [0, 1, 2, 3])
def test_capacidade_tolerante_concorda_com_a_estrita_no_dominio_valido(tamanho):
    assert team.capacidade_bagagem_tolerante(tamanho) == team.capacidade_bagagem(tamanho)


def test_capacidade_tolerante_nao_levanta_com_time_corrompido():
    acima = balance.CAPACIDADE_TOTAL_TREINADOR + 5
    assert team.capacidade_bagagem_tolerante(acima) == 0


def test_capacidade_estrita_continua_recusando_o_invalido():
    # A escrita nao afrouxa: so a leitura tolera, para nao esconder o problema
    # atras de um 500.
    with pytest.raises(team.ErroDeTime):
        team.capacidade_bagagem(balance.CAPACIDADE_TOTAL_TREINADOR + 5)


# --- MEDIO: lista absurda travava linhas antes de ser recusada -----------


def test_pedido_grande_demais_e_recusado_sem_tocar_no_banco():
    ids = [uuid.uuid4() for _ in range(balance.TAMANHO_MAXIMO_TIME + 1)]
    with pytest.raises(team.ErroDeTime) as capturado:
        team.validar_pedido(ids)
    assert capturado.value.codigo == "TIME_CHEIO"


def test_pedido_com_repetido_e_recusado_sem_tocar_no_banco():
    repetido = uuid.uuid4()
    with pytest.raises(team.ErroDeTime) as capturado:
        team.validar_pedido([repetido, repetido])
    assert capturado.value.codigo == "POKEMON_DUPLICADO"


def test_pedido_valido_passa_pela_validacao_barata():
    team.validar_pedido([uuid.uuid4() for _ in range(balance.TAMANHO_MAXIMO_TIME)])


# --- Campos derivados que o cliente deixou de calcular -------------------

pytestmark_banco = pytest.mark.skipif(
    not _banco_disponivel(), reason="Postgres indisponivel; rode com make test-db"
)


def _registrar() -> str:
    usuario = f"f4_{uuid.uuid4().hex[:10]}"
    resposta = cliente.post("/auth/register", json={"usuario": usuario, "senha": "senhavalida123"})
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["token"]


@pytestmark_banco
def test_listagem_informa_ocupado_e_tamanho_maximo_prontos():
    # Sem estes campos o cliente reimplementava o invariante 3 e o tamanho
    # maximo de time por conta propria, contra o Artigo II.
    token = _registrar()
    itens = cliente.get("/trainers", headers={"Authorization": f"Bearer {token}"}).json()["items"]

    assert itens
    for treinador in itens:
        assert treinador["ocupado"] is False
        assert treinador["tamanho_maximo_time"] == balance.TAMANHO_MAXIMO_TIME


@pytestmark_banco
def test_pedido_absurdo_pela_api_devolve_conflito_e_nao_erro_interno():
    token = _registrar()
    cabecalho = {"Authorization": f"Bearer {token}"}
    treinador = cliente.get("/trainers", headers=cabecalho).json()["items"][0]

    resposta = cliente.put(
        f"/trainers/{treinador['id']}/team",
        json={"pokemon_ids": [str(uuid.uuid4()) for _ in range(500)]},
        headers=cabecalho,
    )

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "TIME_CHEIO"


@pytestmark_banco
def test_poder_do_time_chega_ao_cliente_com_casa_decimal():
    token = _registrar()
    cabecalho = {"Authorization": f"Bearer {token}"}
    treinador = cliente.get("/trainers", headers=cabecalho).json()["items"][0]
    pokemon = cliente.get("/pokemon", headers=cabecalho).json()["items"][0]

    detalhe = cliente.put(
        f"/trainers/{treinador['id']}/team",
        json={"pokemon_ids": [pokemon["id"]]},
        headers=cabecalho,
    ).json()

    assert isinstance(detalhe["poder"], float)
