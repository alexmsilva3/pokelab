"""Contrato de `/trainers` (spec 004): os doze criterios de aceite, mais o que
a spec exige mas nao enumera — concorrencia, escopo, codigos de erro e as
rotas que a v1 deliberadamente nao tem.

Cada teste nomeia o comportamento observavel que verifica, nao a forma da
implementacao (Artigo IX): o que conta e o que a spec promete ao professor, e
e por isso que os testes passam pela API HTTP de ponta a ponta, exatamente
como o cliente a usa.

Onde a spec exige um estado que nenhuma rota desta fase produz — treinador em
expedicao, Pokemon de outro laboratorio — o teste forja esse estado direto no
banco, como o proprio plano da Fase 4 prescreve.
"""

from __future__ import annotations

import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from app.core.database import SessionLocal, engine
from app.core.erros import ConflitoDeTime
from app.game import balance
from app.main import app
from app.models import PokemonInstancia, Treinador
from app.services import trainers as trainers_service
from tests.conftest import requer_banco

pytestmark = requer_banco

client = TestClient(app)


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


def _ficha(sessao: dict, treinador_id: str) -> dict:
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


def _prever_time(sessao: dict, treinador_id: str, pokemon_ids: list[str]):
    return client.post(
        f"/trainers/{treinador_id}/team/preview",
        json={"pokemon_ids": pokemon_ids},
        headers=_cabecalho(sessao),
    )


def _inserir_pokemon_livre(sessao_db, laboratorio_id: uuid.UUID, *, especie_id: int = 4) -> str:
    """Um Pokemon livre a mais, para cenarios que exigem mais do que os tres
    starters com que o laboratorio nasce."""
    pokemon = PokemonInstancia(
        laboratorio_id=laboratorio_id,
        especie_id=especie_id,
        nivel=5,
        experiencia=0,
        hp_atual_pct=100,
        hp_atualizado_em=datetime.now(UTC),
        origem="CAPTURADO",
        local_captura_id=None,
        capturado_em=datetime.now(UTC),
    )
    sessao_db.add(pokemon)
    sessao_db.flush()
    sessao_db.commit()
    return str(pokemon.id)


def _forjar_status(sessao_db, treinador_id: str, status: str) -> None:
    """Nada nesta fase produz um treinador ocupado: forja-se o estado direto
    no banco, como o plano da Fase 4 pede para o criterio 6."""
    treinador = sessao_db.get(Treinador, uuid.UUID(treinador_id))
    treinador.status = status
    sessao_db.commit()


@contextmanager
def contar_consultas():
    contagem = {"total": 0}

    def _ouvir(conn, cursor, statement, parameters, context, executemany):
        contagem["total"] += 1

    event.listen(engine, "before_cursor_execute", _ouvir)
    try:
        yield contagem
    finally:
        event.remove(engine, "before_cursor_execute", _ouvir)


# --- Criterio 1 ----------------------------------------------------------------
# Laboratorio recem-criado: tres treinadores, nivel 1, sem Pokemon, disponiveis.


def test_laboratorio_recem_criado_tem_treinadores_de_nivel_1_sem_pokemon_e_disponiveis(sessao_db):
    sessao = _registrar("Ash")

    itens = _treinadores(sessao)

    assert len(itens) == balance.TREINADORES_NO_KIT_INICIAL
    for treinador in itens:
        assert treinador["nivel"] == 1
        assert treinador["experiencia"] == 0
        assert treinador["status"] == "DISPONIVEL"
        assert treinador["time"] == []
        assert treinador["capacidade_bagagem"] == balance.CAPACIDADE_TOTAL_TREINADOR
        assert treinador["nome"]
        assert treinador["avatar"]["iniciais"]


# --- Criterio 1 (regressao da revisao da Fase 4): campos derivados -------------
# Sem estes campos o cliente reimplementava o invariante 3 e o tamanho maximo
# de time por conta propria, contra o Artigo II.


def test_listagem_informa_ocupado_e_tamanho_maximo_prontos(sessao_db):
    sessao = _registrar("CamposDerivados")
    itens = _treinadores(sessao)

    assert itens
    for treinador in itens:
        assert treinador["ocupado"] is False
        assert treinador["tamanho_maximo_time"] == balance.TAMANHO_MAXIMO_TIME


# --- Criterio 2 ----------------------------------------------------------------
# Atribuir dois Pokemon livres: o time passa a ter os dois, e eles somem dos
# livres.


def test_atribuir_dois_pokemon_livres_forma_o_time_e_os_retira_dos_livres(sessao_db):
    sessao = _registrar("Misty")
    treinador_id = _treinadores(sessao)[0]["id"]
    livres_antes = _pokemon_livres(sessao)
    escolhidos = [livres_antes[0]["id"], livres_antes[1]["id"]]

    resposta = _definir_time(sessao, treinador_id, escolhidos)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert {p["id"] for p in corpo["time"]} == set(escolhidos)
    assert corpo["capacidade_bagagem"] == balance.CAPACIDADE_TOTAL_TREINADOR - len(escolhidos)
    ids_livres_depois = {p["id"] for p in _pokemon_livres(sessao)}
    assert ids_livres_depois.isdisjoint(escolhidos)


# --- Criterio 3 ----------------------------------------------------------------
# Reduzir o time de dois para um: quem saiu volta a ficar livre (e a
# substituicao total do plano.md).


def test_reduzir_o_time_de_dois_para_um_devolve_o_excedente_aos_livres(sessao_db):
    sessao = _registrar("Brock")
    treinador_id = _treinadores(sessao)[0]["id"]
    dois = [p["id"] for p in _pokemon_livres(sessao)[:2]]
    _definir_time(sessao, treinador_id, dois)

    resposta = _definir_time(sessao, treinador_id, [dois[0]])

    assert resposta.status_code == 200
    assert [p["id"] for p in resposta.json()["time"]] == [dois[0]]
    ids_livres_depois = {p["id"] for p in _pokemon_livres(sessao)}
    assert dois[1] in ids_livres_depois


# --- Criterio 4 ----------------------------------------------------------------
# Lista maior que o maximo do time: recusada, time anterior intacto.


def test_lista_acima_do_maximo_do_time_e_recusada_e_o_time_anterior_permanece(sessao_db):
    sessao = _registrar("Gary")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinadores(sessao)[0]["id"]
    primeiro = _pokemon_livres(sessao)[0]["id"]
    _definir_time(sessao, treinador_id, [primeiro])

    necessarios = balance.TAMANHO_MAXIMO_TIME + 1
    candidatos = [p["id"] for p in _pokemon_livres(sessao)]
    while len(candidatos) + 1 < necessarios:
        candidatos.append(_inserir_pokemon_livre(sessao_db, laboratorio_id))
    composicao = [primeiro, *candidatos[: necessarios - 1]]
    assert len(composicao) == necessarios

    resposta = _definir_time(sessao, treinador_id, composicao)

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "TIME_CHEIO"
    assert [p["id"] for p in _ficha(sessao, treinador_id)["time"]] == [primeiro]


# --- Criterio 4 (regressao da revisao da Fase 4): lista absurda nao derruba ----
# MEDIO: uma lista absurdamente grande travava linhas do banco antes de ser
# recusada; a validacao barata de tamanho tem de vir ANTES de qualquer
# consulta, e a API devolve 409, nunca 500.


def test_pedido_absurdo_pela_api_devolve_conflito_e_nao_erro_interno(sessao_db):
    sessao = _registrar("PedidoAbsurdo")
    treinador_id = _treinadores(sessao)[0]["id"]

    resposta = _definir_time(sessao, treinador_id, [str(uuid.uuid4()) for _ in range(500)])

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "TIME_CHEIO"


# --- Criterio 5 ----------------------------------------------------------------
# Pokemon ja no time de outro treinador: recusado, nada muda nos dois times.


def test_pokemon_de_outro_treinador_e_recusado_sem_mudar_nenhum_dos_dois_times(sessao_db):
    sessao = _registrar("Erika")
    treinador_a, treinador_b = _treinadores(sessao)[:2]
    livres = _pokemon_livres(sessao)
    alvo, outro = livres[0]["id"], livres[1]["id"]
    _definir_time(sessao, treinador_a["id"], [alvo])

    resposta = _definir_time(sessao, treinador_b["id"], [alvo, outro])

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "POKEMON_JA_ATRIBUIDO"
    assert [p["id"] for p in _ficha(sessao, treinador_a["id"])["time"]] == [alvo]
    assert _ficha(sessao, treinador_b["id"])["time"] == []


# --- Criterio 6 ----------------------------------------------------------------
# Treinador em expedicao: a mudanca e recusada com motivo explicito, e o time
# que ele ja tinha continua intacto.


def test_treinador_em_expedicao_recusa_mudanca_de_time_com_motivo_e_mantem_o_time(sessao_db):
    sessao = _registrar("Sabrina")
    treinador_id = _treinadores(sessao)[0]["id"]
    outro_livre = _pokemon_livres(sessao)
    tinha = outro_livre[0]["id"]
    _definir_time(sessao, treinador_id, [tinha])
    _forjar_status(sessao_db, treinador_id, "EM_EXPEDICAO")

    resposta = _definir_time(sessao, treinador_id, [outro_livre[1]["id"]])

    assert resposta.status_code == 409
    corpo = resposta.json()
    assert corpo["erro"]["codigo"] == "TREINADOR_OCUPADO"
    assert "expedicao" in corpo["erro"]["mensagem"]


# --- Criterios 7 e 8 -------------------------------------------------------------
# Capacidade de bagagem: seis menos o tamanho do time.


def test_capacidade_de_bagagem_com_time_de_tres_e_de_um(sessao_db):
    sessao = _registrar("Giovanni")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_a, treinador_b = _treinadores(sessao)[:2]
    livres = [p["id"] for p in _pokemon_livres(sessao)]
    quarto = _inserir_pokemon_livre(sessao_db, laboratorio_id)

    _definir_time(sessao, treinador_a["id"], livres[: balance.TAMANHO_MAXIMO_TIME])
    cheio = _ficha(sessao, treinador_a["id"])
    assert cheio["capacidade_bagagem"] == (
        balance.CAPACIDADE_TOTAL_TREINADOR - balance.TAMANHO_MAXIMO_TIME
    )

    _definir_time(sessao, treinador_b["id"], [quarto])
    um = _ficha(sessao, treinador_b["id"])
    assert um["capacidade_bagagem"] == balance.CAPACIDADE_TOTAL_TREINADOR - 1


# --- Criterio 9 ----------------------------------------------------------------
# Mesmo time, treinadores de nivel diferente: poder maior para o de nivel maior.


def test_poder_do_time_e_maior_para_o_treinador_de_nivel_maior(sessao_db):
    sessao = _registrar("Lance")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_a, treinador_b = _treinadores(sessao)[:2]
    pokemon_a = _inserir_pokemon_livre(sessao_db, laboratorio_id)
    pokemon_b = _inserir_pokemon_livre(sessao_db, laboratorio_id)
    treinador_b_modelo = sessao_db.get(Treinador, uuid.UUID(treinador_b["id"]))
    treinador_b_modelo.nivel = 20
    sessao_db.commit()

    _definir_time(sessao, treinador_a["id"], [pokemon_a])
    _definir_time(sessao, treinador_b["id"], [pokemon_b])

    ficha_a = _ficha(sessao, treinador_a["id"])
    ficha_b = _ficha(sessao, treinador_b["id"])
    assert ficha_b["poder"] > ficha_a["poder"]


# --- Criterio 9 (regressao da revisao da Fase 4): poder chega com decimal -----
# Inteiro escondia o bonus do treinador em times pequenos (ver
# test_game_power.py); este confere que o CLIENTE recebe o float, nao um
# inteiro truncado.


def test_poder_do_time_chega_ao_cliente_com_casa_decimal(sessao_db):
    sessao = _registrar("PoderComCasaDecimal")
    treinador_id = _treinadores(sessao)[0]["id"]
    pokemon_id = _pokemon_livres(sessao)[0]["id"]

    detalhe = _definir_time(sessao, treinador_id, [pokemon_id]).json()

    assert isinstance(detalhe["poder"], float)


# --- Criterio 10 ---------------------------------------------------------------
# Identificador de treinador de outro professor: 404.


def test_treinador_de_outro_professor_devolve_404(sessao_db):
    sessao_oak = _registrar("Oak")
    sessao_elm = _registrar("Elm")
    treinador_de_oak = _treinadores(sessao_oak)[0]["id"]

    resposta = client.get(f"/trainers/{treinador_de_oak}", headers=_cabecalho(sessao_elm))

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"


def test_treinador_inexistente_devolve_404(sessao_db):
    sessao = _registrar("Oak2")

    resposta = client.get(f"/trainers/{uuid.uuid4()}", headers=_cabecalho(sessao))

    assert resposta.status_code == 404


# --- Criterio 11 ---------------------------------------------------------------
# Pokemon repetido na lista: recusado.


def test_lista_com_pokemon_repetido_e_recusada(sessao_db):
    sessao = _registrar("Whitney")
    treinador_id = _treinadores(sessao)[0]["id"]
    livre = _pokemon_livres(sessao)[0]["id"]

    resposta = _definir_time(sessao, treinador_id, [livre, livre])

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "POKEMON_DUPLICADO"


# --- Criterio 12 ---------------------------------------------------------------
# O time definido sobrevive a releitura.


def test_time_definido_continua_o_mesmo_apos_recarregar_a_pagina(sessao_db):
    sessao = _registrar("Clair")
    treinador_id = _treinadores(sessao)[0]["id"]
    dois = [p["id"] for p in _pokemon_livres(sessao)[:2]]
    _definir_time(sessao, treinador_id, dois)

    primeira_leitura = _ficha(sessao, treinador_id)
    segunda_leitura = _ficha(sessao, treinador_id)

    assert {p["id"] for p in primeira_leitura["time"]} == set(dois)
    assert primeira_leitura["time"] == segunda_leitura["time"]


# --- Alem dos doze, item 1: concorrencia (Artigo VII) -------------------------
#
# Dois treinadores DIFERENTES disputando o MESMO Pokemon livre: ao final, o
# Pokemon pertence a exatamente um dos dois, e o outro PUT falhou com um erro
# claro. Mesmo padrao de `test_services_auth.py`: threads reais, uma
# sessao de banco propria por thread, e uma barreira para garantir que os dois
# comecem juntos — sem ela, o primeiro poderia terminar antes do segundo nem
# comecar, e a corrida nunca aconteceria.


def test_dois_treinadores_disputando_o_mesmo_pokemon_tem_exatamente_um_sucesso(sessao_db):
    sessao = _registrar("Concorrente")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_a, treinador_b = (uuid.UUID(t["id"]) for t in _treinadores(sessao)[:2])
    alvo = uuid.UUID(_pokemon_livres(sessao)[0]["id"])

    resultados: list[tuple[str, str]] = []
    trava = threading.Lock()
    partida = threading.Barrier(2)

    def tentar(treinador_id: uuid.UUID) -> None:
        partida.wait()
        with SessionLocal() as sessao_local:
            try:
                trainers_service.definir_time(sessao_local, laboratorio_id, treinador_id, [alvo])
            except ConflitoDeTime as erro:
                with trava:
                    resultados.append(("erro", erro.codigo))
                return
        with trava:
            resultados.append(("ok", str(treinador_id)))

    threads = [
        threading.Thread(target=tentar, args=(treinador_a,)),
        threading.Thread(target=tentar, args=(treinador_b,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    sucessos = [r for r in resultados if r[0] == "ok"]
    falhas = [r for r in resultados if r[0] == "erro"]
    assert len(sucessos) == 1, resultados
    assert len(falhas) == 1, resultados
    assert falhas[0][1] == "POKEMON_JA_ATRIBUIDO"

    dono_final = sessao_db.get(PokemonInstancia, alvo).treinador_id
    assert dono_final in (treinador_a, treinador_b)


# --- Alem dos doze, item 2: previa e salvamento concordam ---------------------
#
# A previa (`POST .../preview`) e o salvamento (`PUT .../team`) chamam a mesma
# funcao de dominio (plan.md, secao 6). Parametrizado para que uma divergencia
# futura entre os dois seja pega aqui, nao em producao.


def _cenario_composicao_valida(sessao, sessao_db, laboratorio_id):
    treinador_id = _treinadores(sessao)[0]["id"]
    livres = _pokemon_livres(sessao)
    return treinador_id, [livres[0]["id"], livres[1]["id"]], True, None


def _cenario_time_acima_do_maximo(sessao, sessao_db, laboratorio_id):
    treinador_id = _treinadores(sessao)[0]["id"]
    candidatos = [p["id"] for p in _pokemon_livres(sessao)]
    necessarios = balance.TAMANHO_MAXIMO_TIME + 1
    while len(candidatos) < necessarios:
        candidatos.append(_inserir_pokemon_livre(sessao_db, laboratorio_id))
    return treinador_id, candidatos[:necessarios], False, "TIME_CHEIO"


def _cenario_pokemon_de_outro_treinador(sessao, sessao_db, laboratorio_id):
    treinador_a, treinador_b = _treinadores(sessao)[:2]
    alvo = _pokemon_livres(sessao)[0]["id"]
    _definir_time(sessao, treinador_a["id"], [alvo])
    return treinador_b["id"], [alvo], False, "POKEMON_JA_ATRIBUIDO"


def _cenario_pokemon_repetido(sessao, sessao_db, laboratorio_id):
    treinador_id = _treinadores(sessao)[0]["id"]
    livre = _pokemon_livres(sessao)[0]["id"]
    return treinador_id, [livre, livre], False, "POKEMON_DUPLICADO"


CENARIOS_DE_COMPOSICAO = [
    pytest.param(_cenario_composicao_valida, id="composicao-valida"),
    pytest.param(_cenario_time_acima_do_maximo, id="time-acima-do-maximo"),
    pytest.param(_cenario_pokemon_de_outro_treinador, id="pokemon-de-outro-treinador"),
    pytest.param(_cenario_pokemon_repetido, id="pokemon-repetido"),
]


@pytest.mark.parametrize("montar_cenario", CENARIOS_DE_COMPOSICAO)
def test_previa_e_salvamento_concordam_no_veredito(sessao_db, montar_cenario):
    sessao = _registrar(f"cenario-{montar_cenario.__name__}")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id, pokemon_ids, valido_esperado, codigo_esperado = montar_cenario(
        sessao, sessao_db, laboratorio_id
    )

    previa = _prever_time(sessao, treinador_id, pokemon_ids)
    resultado = _definir_time(sessao, treinador_id, pokemon_ids)

    assert previa.status_code == 200
    assert previa.json()["valido"] is valido_esperado
    if valido_esperado:
        assert resultado.status_code == 200
        assert previa.json()["codigo"] is None
    else:
        assert resultado.status_code == 409
        assert previa.json()["codigo"] == codigo_esperado
        assert resultado.json()["erro"]["codigo"] == codigo_esperado


# --- Alem dos doze, item 5: N+1 em GET /trainers ------------------------------
#
# Listar com os times cheios nao pode custar mais consultas do que listar com
# os times vazios: se custasse, o numero cresceria com a quantidade de
# Pokemon, que e exatamente o N+1 que o plano.md aponta como risco.


def test_listar_treinadores_com_times_cheios_nao_emite_mais_consultas_que_vazios(sessao_db):
    sessao = _registrar("Trio")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])

    with contar_consultas() as vazio:
        resposta_vazia = client.get("/trainers", headers=_cabecalho(sessao))
    assert resposta_vazia.status_code == 200

    treinadores = _treinadores(sessao)
    necessarios = len(treinadores) * balance.TAMANHO_MAXIMO_TIME
    livres = [p["id"] for p in _pokemon_livres(sessao)]
    while len(livres) < necessarios:
        livres.append(_inserir_pokemon_livre(sessao_db, laboratorio_id))
    for indice, treinador in enumerate(treinadores):
        inicio = indice * balance.TAMANHO_MAXIMO_TIME
        fim = inicio + balance.TAMANHO_MAXIMO_TIME
        _definir_time(sessao, treinador["id"], livres[inicio:fim])

    with contar_consultas() as cheio:
        resposta_cheia = client.get("/trainers", headers=_cabecalho(sessao))

    corpo = resposta_cheia.json()["items"]
    assert all(len(t["time"]) == balance.TAMANHO_MAXIMO_TIME for t in corpo)
    assert cheio["total"] == vazio["total"]


# --- Alem dos doze, item 6: escopo em GET, PUT e preview ----------------------


def test_treinador_de_outro_laboratorio_devolve_404_em_get_put_e_preview(sessao_db):
    sessao_a = _registrar("DonoA")
    sessao_b = _registrar("DonoB")
    treinador_de_a = _treinadores(sessao_a)[0]["id"]
    pokemon_de_b = _pokemon_livres(sessao_b)[0]["id"]

    resposta_get = client.get(f"/trainers/{treinador_de_a}", headers=_cabecalho(sessao_b))
    resposta_put = _definir_time(sessao_b, treinador_de_a, [pokemon_de_b])
    resposta_preview = _prever_time(sessao_b, treinador_de_a, [pokemon_de_b])

    assert resposta_get.status_code == 404
    assert resposta_put.status_code == 404
    assert resposta_preview.status_code == 404
    for resposta in (resposta_get, resposta_put, resposta_preview):
        assert resposta.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"


# --- Alem dos doze, item 7: cada violacao tem seu proprio codigo --------------
#
# `POKEMON_COMPROMETIDO` fica de fora: a coluna que o produziria so existe na
# Fase 8 (comprometido_com_entrega e sempre False em services/trainers.py ate
# la), e o invariante ja tem teste proprio no dominio
# (test_game_team.py::test_pokemon_comprometido_com_entrega_nao_entra_em_time).


def test_cada_violacao_de_time_devolve_seu_proprio_codigo_de_erro(sessao_db):
    sessao = _registrar("Codigos")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_a, treinador_b = _treinadores(sessao)[:2]
    necessarios = balance.TAMANHO_MAXIMO_TIME + 1
    livres = [p["id"] for p in _pokemon_livres(sessao)]
    while len(livres) < necessarios:
        livres.append(_inserir_pokemon_livre(sessao_db, laboratorio_id))

    time_cheio = _definir_time(sessao, treinador_a["id"], livres[:necessarios])

    _definir_time(sessao, treinador_a["id"], [livres[0]])
    ja_atribuido = _definir_time(sessao, treinador_b["id"], [livres[0]])

    repetido = _definir_time(sessao, treinador_b["id"], [livres[1], livres[1]])

    desconhecido = _definir_time(sessao, treinador_b["id"], [str(uuid.uuid4())])

    _forjar_status(sessao_db, treinador_b["id"], "EM_EXPEDICAO")
    ocupado = _definir_time(sessao, treinador_b["id"], [livres[2]])

    respostas = {
        "TIME_CHEIO": time_cheio,
        "POKEMON_JA_ATRIBUIDO": ja_atribuido,
        "POKEMON_DUPLICADO": repetido,
        "POKEMON_DESCONHECIDO": desconhecido,
        "TREINADOR_OCUPADO": ocupado,
    }
    for codigo_esperado, resposta in respostas.items():
        assert resposta.status_code == 409, (codigo_esperado, resposta.json())
        assert resposta.json()["erro"]["codigo"] == codigo_esperado

    codigos_distintos = {r.json()["erro"]["codigo"] for r in respostas.values()}
    assert len(codigos_distintos) == len(respostas)


# --- Alem dos doze, item 8: rotas que a v1 nao tem ----------------------------
#
# Regra 12 da spec: nao ha contratacao nem dispensa nesta versao.


def test_post_trainers_nao_cria_treinador(sessao_db):
    sessao = _registrar("SemRecrutamento")
    antes = len(_treinadores(sessao))

    resposta = client.post("/trainers", json={}, headers=_cabecalho(sessao))

    assert resposta.status_code in (404, 405)
    assert len(_treinadores(sessao)) == antes


def test_delete_trainers_nao_apaga_treinador(sessao_db):
    sessao = _registrar("SemDispensa")
    treinador_id = _treinadores(sessao)[0]["id"]

    resposta = client.delete(f"/trainers/{treinador_id}", headers=_cabecalho(sessao))

    assert resposta.status_code in (404, 405)
    assert any(t["id"] == treinador_id for t in _treinadores(sessao))


# --- Alem dos doze, item 9: Pokemon inexistente ou de outro laboratorio ------


def test_pokemon_inexistente_no_put_e_recusado_e_o_time_anterior_permanece(sessao_db):
    sessao = _registrar("Fantasma")
    treinador_id = _treinadores(sessao)[0]["id"]
    livre = _pokemon_livres(sessao)[0]["id"]
    _definir_time(sessao, treinador_id, [livre])

    resposta = _definir_time(sessao, treinador_id, [str(uuid.uuid4())])

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "POKEMON_DESCONHECIDO"
    assert [p["id"] for p in _ficha(sessao, treinador_id)["time"]] == [livre]


def test_pokemon_de_outro_laboratorio_no_put_e_recusado_e_o_time_anterior_permanece(sessao_db):
    sessao_dono = _registrar("DonoLegitimo")
    sessao_intruso = _registrar("Intruso")
    treinador_id = _treinadores(sessao_intruso)[0]["id"]
    pokemon_do_intruso = _pokemon_livres(sessao_intruso)[0]["id"]
    _definir_time(sessao_intruso, treinador_id, [pokemon_do_intruso])
    pokemon_de_outro_lab = _pokemon_livres(sessao_dono)[0]["id"]

    resposta = _definir_time(sessao_intruso, treinador_id, [pokemon_de_outro_lab])

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "POKEMON_DESCONHECIDO"
    assert [p["id"] for p in _ficha(sessao_intruso, treinador_id)["time"]] == [pokemon_do_intruso]


# --- Sem token nao ha nada a ver -----------------------------------------------


def test_sem_token_devolve_401(sessao_db):
    assert client.get("/trainers").status_code == 401
