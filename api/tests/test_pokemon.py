"""Criterios de aceite da spec 003 para o acervo de Pokemon do laboratorio.

Cada teste cobre um criterio por numero (docstring), mais os riscos do
plan.md que uma suite ingenua deixaria passar: N+1 na listagem, escopo em
GET e PATCH, filtro pelo tipo secundario, filtros combinados e o teto de
paginacao. O teste confere o comportamento observavel pela API HTTP, nao a
forma interna da implementacao (Artigo IX).
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.database import engine
from app.game import balance
from app.main import app
from app.models import PokemonInstancia
from app.routers.pokemon import PAGE_MAXIMA
from tests.conftest import requer_banco

pytestmark = requer_banco

client = TestClient(app)


def _registrar(usuario: str) -> dict:
    resposta = client.post("/auth/register", json={"usuario": usuario, "senha": f"{usuario}12345"})
    assert resposta.status_code == 201
    return resposta.json()


def _cabecalho(sessao: dict) -> dict:
    return {"Authorization": f"Bearer {sessao['token']}"}


def _inserir_pokemon(
    sessao_db,
    laboratorio_id: uuid.UUID,
    *,
    especie_id: int,
    nivel: int,
) -> uuid.UUID:
    """Devolve so o id: `commit()` expira os atributos do objeto (ver conftest)."""
    pokemon = PokemonInstancia(
        laboratorio_id=laboratorio_id,
        especie_id=especie_id,
        nivel=nivel,
        experiencia=0,
        hp_atual_pct=100,
        hp_atualizado_em=datetime.now(UTC),
        origem="CAPTURADO",
        capturado_em=datetime.now(UTC),
    )
    sessao_db.add(pokemon)
    sessao_db.flush()
    return pokemon.id


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


# --- Criterio 1 --------------------------------------------------------------


def test_laboratorio_recem_criado_mostra_os_tres_iniciais_com_imagem_nome_tipo_e_nivel(sessao_db):
    sessao = _registrar("Crit01_Ash")

    resposta = client.get("/pokemon", headers=_cabecalho(sessao))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 3
    assert len(corpo["items"]) == 3
    for item in corpo["items"]:
        assert item["nome"]
        assert item["sprite"]
        assert item["tipo_primario"]
        assert item["nivel"] == balance.STARTER_LEVEL


# --- Criterio 2 --------------------------------------------------------------


def test_avancar_de_pagina_mostra_os_seguintes_sem_mudar_o_total(sessao_db):
    sessao = _registrar("Crit02_Misty")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    for _ in range(7):
        _inserir_pokemon(sessao_db, laboratorio_id, especie_id=1, nivel=10)
    sessao_db.commit()

    pagina1 = client.get(
        "/pokemon", params={"page": 1, "page_size": 5}, headers=_cabecalho(sessao)
    ).json()
    pagina2 = client.get(
        "/pokemon", params={"page": 2, "page_size": 5}, headers=_cabecalho(sessao)
    ).json()

    assert pagina1["total"] == pagina2["total"] == 10  # 3 iniciais + 7 inseridos
    assert len(pagina1["items"]) == 5
    assert len(pagina2["items"]) == 5
    ids1 = {item["id"] for item in pagina1["items"]}
    ids2 = {item["id"] for item in pagina2["items"]}
    assert ids1.isdisjoint(ids2)


def test_pagina_acima_do_teto_e_cortada_e_as_paginas_cobrem_tudo_sem_duplicar(sessao_db):
    """Regra do plan.md: page_size acima de 100 e cortado em silencio, nunca recusado."""
    sessao = _registrar("Crit02_Teto")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    for _ in range(120):
        _inserir_pokemon(sessao_db, laboratorio_id, especie_id=1, nivel=10)
    sessao_db.commit()

    primeira = client.get(
        "/pokemon", params={"page": 1, "page_size": 9999}, headers=_cabecalho(sessao)
    ).json()
    assert primeira["page_size"] == 100
    total = primeira["total"]
    assert total == 123  # 3 iniciais + 120 inseridos

    vistos: set[str] = set()
    page = 1
    while len(vistos) < total:
        pagina = client.get(
            "/pokemon",
            params={"page": page, "page_size": primeira["page_size"]},
            headers=_cabecalho(sessao),
        ).json()
        assert pagina["total"] == total
        ids_desta_pagina = {item["id"] for item in pagina["items"]}
        assert ids_desta_pagina.isdisjoint(vistos), "um pokemon apareceu em duas paginas"
        if not ids_desta_pagina:
            break
        vistos |= ids_desta_pagina
        page += 1

    assert len(vistos) == total, "a soma das paginas nao cobriu todo o acervo"


# --- Criterio 2 (regressao da revisao da Fase 3): o teto do OFFSET do Postgres -
# ALTO: (page - 1) * page_size passava de 2^63-1, o Postgres recusava o
# OFFSET e a resposta era 500 em texto puro, fora do envelope da aplicacao.


def test_pagina_absurda_e_recusada_sem_derrubar_o_servidor(sessao_db):
    sessao = _registrar("Crit02_PaginaAbsurda")
    resposta = client.get(
        "/pokemon", params={"page": 4611686018427387904}, headers=_cabecalho(sessao)
    )
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "ENTRADA_INVALIDA"


def test_pagina_no_limite_maximo_ainda_responde(sessao_db):
    sessao = _registrar("Crit02_PaginaNoTeto")
    resposta = client.get("/pokemon", params={"page": PAGE_MAXIMA}, headers=_cabecalho(sessao))
    assert resposta.status_code == 200
    assert resposta.json()["items"] == []


def test_pagina_alem_do_fim_devolve_lista_vazia_e_total_correto(sessao_db):
    sessao = _registrar("Crit02_PaginaAlemDoFim")
    resposta = client.get("/pokemon", params={"page": 99}, headers=_cabecalho(sessao))
    corpo = resposta.json()

    assert resposta.status_code == 200
    assert corpo["items"] == []
    # O total continua sendo o do acervo, para a interface saber que a pagina e
    # que esta fora de faixa, e nao o filtro que nao achou nada.
    assert corpo["total"] == len(balance.STARTER_SPECIES_IDS)


# --- Criterio 3 ----------------------------------------------------------------


def test_filtro_por_tipo_traz_pokemon_que_tem_aquele_tipo_como_secundario(sessao_db):
    """Bulbasaur e grass/poison: filtrar por poison tem que traze-lo."""
    sessao = _registrar("Crit03_Brock")

    resposta = client.get("/pokemon", params={"tipo": "poison"}, headers=_cabecalho(sessao))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["total"] == 1
    item = corpo["items"][0]
    assert item["especie_id"] == 1
    assert item["tipo_secundario"] == "poison"


# --- Criterio 4 ----------------------------------------------------------------


def test_filtros_de_tipo_e_faixa_de_nivel_combinados_satisfazem_os_dois(sessao_db):
    sessao = _registrar("Crit04_Dawn")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    _inserir_pokemon(sessao_db, laboratorio_id, especie_id=1, nivel=8)  # grass, nivel baixo
    alvo = _inserir_pokemon(sessao_db, laboratorio_id, especie_id=1, nivel=42)  # grass, nivel alto
    _inserir_pokemon(sessao_db, laboratorio_id, especie_id=4, nivel=42)  # fire, nivel alto
    sessao_db.commit()

    resposta = client.get(
        "/pokemon",
        params={"tipo": "grass", "nivel_min": 30, "nivel_max": 50},
        headers=_cabecalho(sessao),
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    ids = {item["id"] for item in corpo["items"]}
    assert str(alvo) in ids
    assert all(30 <= item["nivel"] <= 50 for item in corpo["items"])
    assert all(
        "grass" in (item["tipo_primario"], item["tipo_secundario"]) for item in corpo["items"]
    )


# --- Criterio 5 ----------------------------------------------------------------


def test_ficha_de_pokemon_nivel_5_mostra_os_stats_calculados_para_o_nivel_e_nao_os_da_especie(
    sessao_db,
):
    sessao = _registrar("Crit05_Lucas")
    lista = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    bulbasaur_id = next(item["id"] for item in lista["items"] if item["especie_id"] == 1)

    resposta = client.get(f"/pokemon/{bulbasaur_id}", headers=_cabecalho(sessao))

    assert resposta.status_code == 200
    corpo = resposta.json()
    # Tabela conhecida (SDD 4.2): Bulbasaur nivel 5 jamais os stats-base da especie.
    assert corpo["stats"] == {
        "hp": 19,
        "ataque": 9,
        "defesa": 9,
        "ataque_especial": 11,
        "defesa_especial": 11,
        "velocidade": 9,
    }
    assert corpo["hp_atual"] == 19
    assert corpo["hp_maximo"] == 19


# --- Criterio 6 ----------------------------------------------------------------


def test_ficha_no_nivel_maximo_informa_que_nao_ha_proximo_nivel_em_vez_de_numero(sessao_db):
    sessao = _registrar("Crit06_Gary")
    lista = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    pokemon_id = lista["items"][0]["id"]

    instancia = sessao_db.get(PokemonInstancia, uuid.UUID(pokemon_id))
    instancia.nivel = balance.NIVEL_MAXIMO
    instancia.experiencia = 999_999_999
    sessao_db.commit()

    resposta = client.get(f"/pokemon/{pokemon_id}", headers=_cabecalho(sessao))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["nivel_maximo"] is True
    assert corpo["experiencia_para_proximo_nivel"] is None


def test_ficha_abaixo_do_nivel_maximo_sempre_mostra_um_numero_positivo_de_experiencia(sessao_db):
    sessao = _registrar("Crit06_Oposto")
    lista = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    pokemon_id = lista["items"][0]["id"]

    resposta = client.get(f"/pokemon/{pokemon_id}", headers=_cabecalho(sessao))

    corpo = resposta.json()
    assert corpo["nivel_maximo"] is False
    assert isinstance(corpo["experiencia_para_proximo_nivel"], int)
    assert corpo["experiencia_para_proximo_nivel"] > 0


# --- Criterio 7 ----------------------------------------------------------------


def test_apelido_novo_aparece_na_lista_e_na_ficha_e_apagar_devolve_o_nome_da_especie(sessao_db):
    sessao = _registrar("Crit07_May")
    lista = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    pokemon_id = lista["items"][0]["id"]
    especie_nome = lista["items"][0]["especie_nome"]

    renomear = client.patch(
        f"/pokemon/{pokemon_id}", json={"apelido": "Fofinho"}, headers=_cabecalho(sessao)
    )
    assert renomear.status_code == 200
    assert renomear.json()["nome"] == "Fofinho"

    ficha = client.get(f"/pokemon/{pokemon_id}", headers=_cabecalho(sessao)).json()
    assert ficha["nome"] == "Fofinho"

    lista_depois = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    item = next(i for i in lista_depois["items"] if i["id"] == pokemon_id)
    assert item["nome"] == "Fofinho"

    limpar = client.patch(
        f"/pokemon/{pokemon_id}", json={"apelido": None}, headers=_cabecalho(sessao)
    )
    assert limpar.status_code == 200
    assert limpar.json()["nome"] == especie_nome


def test_apelido_composto_apenas_de_espacos_e_recusado(sessao_db):
    sessao = _registrar("Crit07_SoEspaco")
    lista = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    pokemon_id = lista["items"][0]["id"]

    resposta = client.patch(
        f"/pokemon/{pokemon_id}", json={"apelido": "   "}, headers=_cabecalho(sessao)
    )

    assert resposta.status_code == 422


def test_apelido_com_mais_de_cinquenta_caracteres_e_recusado(sessao_db):
    sessao = _registrar("Crit07_Longo")
    lista = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    pokemon_id = lista["items"][0]["id"]

    resposta = client.patch(
        f"/pokemon/{pokemon_id}", json={"apelido": "x" * 51}, headers=_cabecalho(sessao)
    )

    assert resposta.status_code == 422


# --- Criterio 7 (regressao da revisao da Fase 3): apelido cru ------------------
# BAIXO: o cliente deduzia "tem apelido" comparando nome com especie. A
# deducao errava quem apelidasse um Pidgey de "Pidgey": o campo aparecia
# vazio e o proximo salvar apagaria o apelido.


def test_a_ficha_devolve_o_apelido_cru_alem_do_nome_resolvido(sessao_db):
    sessao = _registrar("Crit07_ApelidoCru")
    primeiro = client.get("/pokemon", headers=_cabecalho(sessao)).json()["items"][0]

    sem_apelido = client.get(f"/pokemon/{primeiro['id']}", headers=_cabecalho(sessao)).json()
    assert sem_apelido["apelido"] is None
    assert sem_apelido["nome"] == sem_apelido["especie_nome"]

    especie = sem_apelido["especie_nome"]
    client.patch(
        f"/pokemon/{primeiro['id']}", json={"apelido": especie}, headers=_cabecalho(sessao)
    )
    com_apelido = client.get(f"/pokemon/{primeiro['id']}", headers=_cabecalho(sessao)).json()

    # O caso que quebrava a deducao: apelido identico ao nome da especie.
    assert com_apelido["apelido"] == especie
    assert com_apelido["nome"] == especie


def test_apelido_cru_volta_a_ser_nulo_quando_limpo(sessao_db):
    sessao = _registrar("Crit07_ApelidoCruLimpo")
    primeiro = client.get("/pokemon", headers=_cabecalho(sessao)).json()["items"][0]

    client.patch(
        f"/pokemon/{primeiro['id']}", json={"apelido": "Folhinha"}, headers=_cabecalho(sessao)
    )
    limpo = client.patch(
        f"/pokemon/{primeiro['id']}", json={"apelido": None}, headers=_cabecalho(sessao)
    ).json()

    assert limpo["apelido"] is None
    assert limpo["nome"] == limpo["especie_nome"]


def test_apelido_cru_aparece_tambem_na_listagem(sessao_db):
    sessao = _registrar("Crit07_ApelidoCruLista")
    primeiro = client.get("/pokemon", headers=_cabecalho(sessao)).json()["items"][0]
    assert "apelido" in primeiro

    client.patch(
        f"/pokemon/{primeiro['id']}", json={"apelido": "Folhinha"}, headers=_cabecalho(sessao)
    )
    lista = client.get("/pokemon", headers=_cabecalho(sessao)).json()["items"]
    renomeado = next(item for item in lista if item["id"] == primeiro["id"])

    assert renomeado["apelido"] == "Folhinha"
    assert renomeado["nome"] == "Folhinha"


# --- Criterio 10 ---------------------------------------------------------------


def test_pokemon_inexistente_devolve_404(sessao_db):
    sessao = _registrar("Crit10_Inexistente")

    resposta = client.get(f"/pokemon/{uuid.uuid4()}", headers=_cabecalho(sessao))

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"


def test_pedir_pokemon_de_outro_professor_responde_404_no_get_e_no_patch(sessao_db):
    """Criterio 10: nunca 403, nunca 200 — e o pokemon do outro fica intacto."""
    sessao_a = _registrar("Crit10_ProfA")
    sessao_b = _registrar("Crit10_ProfB")
    lista_b = client.get("/pokemon", headers=_cabecalho(sessao_b)).json()
    pokemon_de_b = lista_b["items"][0]["id"]

    resposta_get = client.get(f"/pokemon/{pokemon_de_b}", headers=_cabecalho(sessao_a))
    resposta_patch = client.patch(
        f"/pokemon/{pokemon_de_b}", json={"apelido": "Roubado"}, headers=_cabecalho(sessao_a)
    )

    assert resposta_get.status_code == 404
    assert resposta_get.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"
    assert resposta_patch.status_code == 404
    assert resposta_patch.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"

    ficha_real = client.get(f"/pokemon/{pokemon_de_b}", headers=_cabecalho(sessao_b)).json()
    assert ficha_real["nome"] != "Roubado"


# --- Criterio 12 (parte que cabe aqui: a origem do sprite) ---------------------


def test_sprite_de_um_pokemon_da_lista_responde_200_com_cache_imutavel(sessao_db):
    sessao = _registrar("Crit12_Sprite")
    lista = client.get("/pokemon", headers=_cabecalho(sessao)).json()
    sprite = lista["items"][0]["sprite"]

    resposta = client.get(f"/sprites/{sprite}")

    assert resposta.status_code == 200
    assert resposta.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert resposta.headers["content-type"] == "image/png"


def test_caminho_de_sprite_com_travessia_de_diretorio_nao_escapa_do_acervo():
    """Um caminho com `..` nao pode servir arquivo nenhum fora de data/sprites."""
    for tentativa in ("/sprites/../../pyproject.toml", "/sprites/%2e%2e/%2e%2e/pyproject.toml"):
        resposta = client.get(tentativa)
        assert resposta.status_code == 404
        assert "pokelab-api" not in resposta.text


# --- Validacao de entrada (regra 3 do plan.md: tipo so aceita um dos dezoito) ---


def test_filtro_de_tipo_desconhecido_e_recusado_em_vez_de_devolver_lista_vazia(sessao_db):
    sessao = _registrar("Crit03_TipoInvalido")

    resposta = client.get("/pokemon", params={"tipo": "nao-existe"}, headers=_cabecalho(sessao))

    assert resposta.status_code == 422


# --- MEDIO (regressao da revisao da Fase 3): nivel fora de faixa -----------
# O nivel fora de faixa e recusado com envelope, nunca com 500.


@pytest.mark.parametrize("parametros", [{"nivel_min": 0}, {"nivel_max": 0}, {"nivel_min": 101}])
def test_nivel_fora_de_faixa_devolve_envelope_de_entrada_invalida(parametros, sessao_db):
    sessao = _registrar("Crit04_NivelForaDeFaixa")
    resposta = client.get("/pokemon", params=parametros, headers=_cabecalho(sessao))
    assert resposta.status_code == 422
    assert resposta.json()["erro"]["codigo"] == "ENTRADA_INVALIDA"


def test_nivel_minimo_maior_que_maximo_devolve_lista_vazia_e_nao_erro(sessao_db):
    sessao = _registrar("Crit04_NivelMinMaiorQueMax")
    resposta = client.get(
        "/pokemon", params={"nivel_min": 50, "nivel_max": 10}, headers=_cabecalho(sessao)
    )
    assert resposta.status_code == 200
    assert resposta.json()["items"] == []


def test_sem_token_devolve_401(sessao_db):
    assert client.get("/pokemon").status_code == 401


# --- N+1: o risco central do plan.md --------------------------------------


def test_listagem_de_pokemon_emite_numero_constante_de_consultas_qualquer_que_seja_a_pagina(
    sessao_db,
):
    """O numero de consultas nao pode crescer com o tamanho da pagina.

    Uma listagem feita com `especie` lazy vira uma consulta por item (N+1): com
    10 Pokemon na pagina e 50 na pagina, o numero de consultas cresceria junto.
    Compara os dois tamanhos de pagina sobre o MESMO acervo de 50+ Pokemon: se
    a contagem for identica, o join e unico.
    """
    sessao = _registrar("CritN1_Oak")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    for _ in range(50):
        _inserir_pokemon(sessao_db, laboratorio_id, especie_id=1, nivel=10)
    sessao_db.commit()

    with _contar_consultas() as contagem_pequena:
        resposta_pequena = client.get(
            "/pokemon", params={"page_size": 10}, headers=_cabecalho(sessao)
        )
    assert resposta_pequena.status_code == 200
    assert len(resposta_pequena.json()["items"]) == 10

    with _contar_consultas() as contagem_grande:
        resposta_grande = client.get(
            "/pokemon", params={"page_size": 50}, headers=_cabecalho(sessao)
        )
    assert resposta_grande.status_code == 200
    assert len(resposta_grande.json()["items"]) == 50

    assert contagem_pequena["total"] == contagem_grande["total"], (
        "a contagem de consultas cresceu com o tamanho da pagina: ha N+1 na listagem"
    )
    # Com 50 itens na pagina, uma consulta por item chegaria perto de 50;
    # o numero real (autenticacao + contagem + pagina) fica bem abaixo disso.
    assert contagem_grande["total"] < 10
