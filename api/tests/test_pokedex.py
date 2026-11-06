"""Criterios de aceite da spec 003 para `GET /pokedex`.

O risco central (plan.md) e o nome de uma especie nunca vista vazar no corpo
da resposta. O teste de vazamento busca o nome no proprio seed em vez de usar
um literal, para nao depender de qual especie o acervo chama de "nunca vista".
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.game import balance
from app.main import app
from app.models import PokedexEntrada, PokemonEspecie
from tests.conftest import requer_banco

pytestmark = requer_banco

client = TestClient(app)


def _registrar(usuario: str) -> dict:
    resposta = client.post("/auth/register", json={"usuario": usuario, "senha": f"{usuario}12345"})
    assert resposta.status_code == 201
    return resposta.json()


def _cabecalho(sessao: dict) -> dict:
    return {"Authorization": f"Bearer {sessao['token']}"}


# --- Criterio 8 ----------------------------------------------------------------


def test_pokedex_de_laboratorio_recem_criado_tem_151_entradas_tres_capturadas_e_as_demais_desconhecidas(
    sessao_db,
):
    sessao = _registrar("Crit08_Dex")

    resposta = client.get("/pokedex", headers=_cabecalho(sessao))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert len(corpo["items"]) == 151
    assert corpo["capturadas"] == 3

    por_estado: dict[str, int] = {}
    for item in corpo["items"]:
        por_estado[item["estado"]] = por_estado.get(item["estado"], 0) + 1

    assert por_estado.get("CAPTURADA", 0) == 3
    assert por_estado.get("DESCONHECIDA", 0) == 148
    assert por_estado.get("VISTA", 0) == 0


def test_numeros_da_pokedex_cobrem_de_um_a_cento_e_cinquenta_e_um_sem_lacuna_nem_repeticao(
    sessao_db,
):
    sessao = _registrar("Crit08_Numeros")

    corpo = client.get("/pokedex", headers=_cabecalho(sessao)).json()

    numeros = [item["numero"] for item in corpo["items"]]
    assert sorted(numeros) == list(range(1, 152))


# --- Criterio 9: o nome nunca vazado -------------------------------------------


def test_especie_nunca_vista_nao_revela_nome_nem_tipo_apenas_numero_e_estado(sessao_db):
    sessao = _registrar("Crit09_Forma")

    corpo = client.get("/pokedex", headers=_cabecalho(sessao)).json()

    desconhecidas = [item for item in corpo["items"] if item["estado"] == "DESCONHECIDA"]
    assert desconhecidas, "o laboratorio novo precisa ter especies desconhecidas para o teste valer"
    for entrada in desconhecidas:
        assert set(entrada.keys()) == {"numero", "estado"}


def test_nome_de_especie_nunca_vista_nao_aparece_em_lugar_nenhum_do_corpo_da_resposta(sessao_db):
    """O nome vem do proprio seed (nao e um literal), e a busca varre o JSON cru.

    Mandar os 151 nomes e so nao exibir no campo errado nao bastaria: um nome
    escondido em outro campo ou em metadado ainda seria vazamento. A varredura
    e sobre o texto bruto da resposta, nao sobre as chaves ja conhecidas.
    """
    sessao = _registrar("Crit09_Vazamento")

    especie_nunca_vista = sessao_db.scalar(
        select(PokemonEspecie)
        .where(PokemonEspecie.id.not_in(balance.STARTER_SPECIES_IDS))
        .order_by(PokemonEspecie.id.desc())
        .limit(1)
    )
    assert especie_nunca_vista is not None, "precisa existir alguma especie fora do kit inicial"

    resposta = client.get("/pokedex", headers=_cabecalho(sessao))
    corpo_bruto = resposta.text
    corpo = resposta.json()

    numero_da_especie = especie_nunca_vista.id
    entrada = next(item for item in corpo["items"] if item["numero"] == numero_da_especie)
    assert entrada["estado"] == "DESCONHECIDA"
    assert especie_nunca_vista.nome not in corpo_bruto


# --- A terceira forma do contrato: vista mas nao capturada ---------------------


def test_especie_avistada_mas_nao_capturada_mostra_nome_tipo_e_imagem_mas_nao_quantidade(
    sessao_db,
):
    """Regra 10 da spec: avistada e marcada como nao capturada, com imagem."""
    sessao = _registrar("Crit10Regra_Vista")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])

    especie_avistada = sessao_db.scalar(
        select(PokemonEspecie).where(PokemonEspecie.id.not_in(balance.STARTER_SPECIES_IDS))
    )
    sessao_db.add(
        PokedexEntrada(
            laboratorio_id=laboratorio_id,
            especie_id=especie_avistada.id,
            visto=True,
            capturado=False,
        )
    )
    sessao_db.commit()

    corpo = client.get("/pokedex", headers=_cabecalho(sessao)).json()
    entrada = next(item for item in corpo["items"] if item["numero"] == especie_avistada.id)

    assert entrada["estado"] == "VISTA"
    assert entrada["nome"] == especie_avistada.nome
    assert especie_avistada.tipo_primario in entrada["tipos"]
    assert entrada["sprite"]
    assert "quantidade" not in entrada


def test_entrada_capturada_mostra_quantidade_atual_de_individuos(sessao_db):
    sessao = _registrar("Crit08_Quantidade")

    corpo = client.get("/pokedex", headers=_cabecalho(sessao)).json()
    capturadas = [item for item in corpo["items"] if item["estado"] == "CAPTURADA"]

    assert len(capturadas) == 3
    assert all(item["quantidade"] == 1 for item in capturadas)
    assert all("nome" in item and "tipos" in item and "sprite" in item for item in capturadas)


# --- Escopo --------------------------------------------------------------------


def test_pokedex_e_escopada_ao_laboratorio_da_sessao(sessao_db):
    sessao_a = _registrar("CritEscopo_DexA")
    sessao_b = _registrar("CritEscopo_DexB")
    laboratorio_a = uuid.UUID(sessao_a["laboratorio"]["id"])

    especie_so_de_a = sessao_db.scalar(
        select(PokemonEspecie).where(PokemonEspecie.id.not_in(balance.STARTER_SPECIES_IDS))
    )
    sessao_db.add(
        PokedexEntrada(
            laboratorio_id=laboratorio_a,
            especie_id=especie_so_de_a.id,
            visto=True,
            capturado=False,
        )
    )
    sessao_db.commit()

    corpo_a = client.get("/pokedex", headers=_cabecalho(sessao_a)).json()
    corpo_b = client.get("/pokedex", headers=_cabecalho(sessao_b)).json()

    entrada_a = next(item for item in corpo_a["items"] if item["numero"] == especie_so_de_a.id)
    entrada_b = next(item for item in corpo_b["items"] if item["numero"] == especie_so_de_a.id)

    assert entrada_a["estado"] == "VISTA"
    assert entrada_b["estado"] == "DESCONHECIDA"


def test_sem_token_devolve_401(sessao_db):
    assert client.get("/pokedex").status_code == 401
