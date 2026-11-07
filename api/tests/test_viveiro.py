"""Cobertura de `GET /ranch` e `DELETE /pokemon/{id}` (spec 008): criterios 1 a
12, mais o que so aparece atravessando banco, transacao e HTTP.

`game/viveiro.py` e `game/soltar.py` ja tem a cobertura pura em
`test_game_viveiro.py` e `test_game_soltar.py` (ocupacao, transbordo, a tabela
de recusas do `pode_soltar`). Este arquivo nao repete nada disso (Artigo IX):
o que ele cobre e o que so existe quando se atravessa SERVICO, TRANSACAO e
HTTP — o retrato real do banco apos tres expedicoes, a guarda do despacho que
NAO pode vazar para as saidas do transbordo, e o escopo por laboratorio.

O teste mais importante do arquivo e
`test_viveiro_transbordado_bloqueia_so_o_despacho_e_mais_nada`: a guarda
escapando para reclamar relatorio, aceitar entrega, concluir entrega ou
soltar prende o professor sem saida, e esse e o sintoma — nao um erro no log.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.game import balance
from app.main import app
from app.models import Entrega, Expedicao, ItemEstoque, PokemonInstancia
from app.services import entregas as entregas_service
from app.services import expedicoes as expedicoes_service
from tests.conftest import requer_banco

pytestmark = requer_banco

client = TestClient(app)

LOCAL_ALCANCAVEL = "route-1"  # vizinho de pallet-town, alcancavel por qualquer laboratorio novo
PIDGEY_ID = 16  # unica especie, junto com Rattata, dentro da banda de um laboratorio nivel 1

# Calibrada do mesmo jeito que `test_relatorio.SEMENTE_SUCESSO`: time de um
# Pokemon nivel 5, treinador nivel 1, Route 1, 3 poke-balls na carga ->
# CONCLUIDA_SUCESSO com exatamente 1 captura. O resultado nao muda entre os
# tres iniciais (mesma garantia que `test_relatorio.py` ja documenta).
SEMENTE_UMA_CAPTURA = 0

# Com este gerador, o PRIMEIRO dos tres pedidos sorteados por
# `game.delivery.gerar_pedidos` para um laboratorio nivel 1, novo, com so
# Pallet Town e Route 1 ao alcance, e sempre "2 Pidgey para Pallet Town" —
# descoberto rodando `game.delivery.gerar_pedido` direto contra as mesmas
# candidatas e cidades que um laboratorio novo tem (Artigo III: a mesma
# semente sempre narra a mesma historia).
SEMENTE_PEDIDO_DOIS_PIDGEY = 2


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


def _despachar(sessao: dict, treinador_id: str, local_id: str = LOCAL_ALCANCAVEL, carga=None):
    return client.post(
        "/expeditions",
        json={"treinador_id": treinador_id, "local_id": local_id, "carga": carga or []},
        headers=_cabecalho(sessao),
    )


def _claim_expedicao(sessao: dict, expedicao_id: str):
    return client.post(f"/expeditions/{expedicao_id}/claim", headers=_cabecalho(sessao))


def _viveiro(sessao: dict):
    return client.get("/ranch", headers=_cabecalho(sessao))


def _soltar(sessao: dict, pokemon_id: str):
    return client.delete(f"/pokemon/{pokemon_id}", headers=_cabecalho(sessao))


def _perfil(sessao: dict):
    resposta = client.get("/me", headers=_cabecalho(sessao))
    assert resposta.status_code == 200
    return resposta.json()


def _pokedex(sessao: dict):
    resposta = client.get("/pokedex", headers=_cabecalho(sessao))
    assert resposta.status_code == 200
    return resposta.json()


def _refresh_entregas(sessao: dict):
    return client.post("/deliveries/refresh", headers=_cabecalho(sessao))


def _pedido_de_dois_pidgey(entregas: list[dict]) -> dict:
    """Acha, entre as entregas listadas, a que pede exatamente 2 Pidgey.

    `entregas_repo.listar` ordena por `(gerada_em, id)`: os tres pedidos de
    `SEMENTE_PEDIDO_DOIS_PIDGEY` nascem no MESMO instante, entao o desempate
    e por `id` — um UUID sorteado a cada insercao, sem relacao com a ORDEM em
    que `gerar_pedidos` os sorteou. `items[0]` e portanto qualquer um dos
    tres; e preciso procurar pelo CONTEUDO, nao pela posicao.
    """
    return next(
        entrega
        for entrega in entregas
        if len(entrega["requisitos"]) == 1
        and entrega["requisitos"][0]["especie_nome"] == "Pidgey"
        and entrega["requisitos"][0]["quantidade"] == 2
    )


def _aceitar_entrega(sessao: dict, entrega_id: str, treinador_id: str, pokemon_ids: list[str]):
    return client.post(
        f"/deliveries/{entrega_id}/accept",
        json={"treinador_id": treinador_id, "pokemon_ids": pokemon_ids},
        headers=_cabecalho(sessao),
    )


def _claim_entrega(sessao: dict, entrega_id: str):
    return client.post(f"/deliveries/{entrega_id}/claim", headers=_cabecalho(sessao))


def _fixar_semente_expedicao(monkeypatch, semente: int) -> None:
    """Forca a proxima semente que `despachar()` sorteia (mesmo truque de
    `test_relatorio._fixar_semente`)."""
    monkeypatch.setattr(expedicoes_service.random, "randrange", lambda *_args, s=semente: s)


def _fixar_gerador_de_entregas(monkeypatch, semente: int) -> None:
    """Forca o gerador que `refresh()` usa para sortear a lista inteira.

    `services/entregas.py::refresh` cria `random.Random()` sem seed gravado
    (o pedido e persistido na hora, nunca resolvido depois a partir de uma
    semente) — o mesmo raciocinio de `_fixar_semente_expedicao`, so que
    substituindo o CONSTRUTOR em vez de uma chamada.

    `entregas_service.random` E o modulo `random` (o mesmo objeto, so com
    outro nome local): capturar a classe original ANTES de substituir e
    obrigatorio, ou a lambda chamaria a si mesma e estouraria a recursao.
    """
    classe_original = random.Random
    monkeypatch.setattr(
        entregas_service.random, "Random", lambda *_a, **_k: classe_original(semente)
    )


def _forjar_eta_passado_expedicao(sessao_db, expedicao_id: str) -> None:
    sessao_db.expire_all()
    expedicao = sessao_db.get(Expedicao, uuid.UUID(expedicao_id))
    expedicao.eta = datetime.now(UTC) - timedelta(seconds=1)
    sessao_db.commit()


def _forjar_eta_passado_entrega(sessao_db, entrega_id: str) -> None:
    sessao_db.expire_all()
    entrega = sessao_db.get(Entrega, uuid.UUID(entrega_id))
    entrega.eta = datetime.now(UTC) - timedelta(seconds=1)
    sessao_db.commit()


def _inserir_pokemon_no_viveiro(
    sessao_db, laboratorio_id: uuid.UUID, especie_id: int, *, nivel: int = 3, quantidade: int = 1
) -> list[uuid.UUID]:
    """Insere Pokemon direto no banco, sem passar pela captura de expedicao.

    Apoio de teste, nao caminho de jogo: existe para montar o ESTOQUE que um
    teste de aceite ou de soltura precisa encontrar pronto no viveiro. Como o
    bicho chega la (a captura em si) e coberto por
    `test_tres_expedicoes_resolvidas_transbordam_o_viveiro_e_nenhum_pokemon_se_perde`
    e pela suite da Fase 7; aqui o que se testa e o que acontece DEPOIS.
    """
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


def _contar_pokemon_no_banco(sessao_db, laboratorio_id: uuid.UUID) -> int:
    sessao_db.expire_all()
    return (
        sessao_db.scalar(
            select(func.count())
            .select_from(PokemonInstancia)
            .where(PokemonInstancia.laboratorio_id == laboratorio_id)
        )
        or 0
    )


def _itens_do_laboratorio(sessao_db, laboratorio_id: uuid.UUID) -> dict[str, int]:
    sessao_db.expire_all()
    linhas = sessao_db.scalars(
        select(ItemEstoque).where(ItemEstoque.laboratorio_id == laboratorio_id)
    )
    return {linha.item_id: linha.quantidade for linha in linhas}


# --- Criterio 1 ---------------------------------------------------------------
# Laboratorio recem-criado: o professor ve ocupacao e capacidade.


def test_viveiro_mostra_ocupacao_e_capacidade(sessao_db):
    sessao = _registrar("Criterio1Viveiro")

    resposta = _viveiro(sessao)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["capacidade"] == balance.CAPACIDADE_VIVEIRO
    assert corpo["ocupacao"] == len(balance.STARTER_SPECIES_IDS)
    assert corpo["transbordado"] is False
    assert corpo["lugares_faltando"] == 0
    assert {item["id"] for item in corpo["items"]} == {p["id"] for p in _pokemon_livres(sessao)}


# --- Criterio 2 ----------------------------------------------------------------
# Um time de tres num treinador: esses tres nao contam na ocupacao.


def test_pokemon_em_time_nao_conta_na_ocupacao(sessao_db):
    sessao = _registrar("Criterio2Viveiro")
    treinador_id = _treinadores(sessao)[0]["id"]
    livres = _pokemon_livres(sessao)
    assert len(livres) == len(balance.STARTER_SPECIES_IDS)

    resposta = _definir_time(sessao, treinador_id, [p["id"] for p in livres])
    assert resposta.status_code == 200

    corpo = _viveiro(sessao).json()
    assert corpo["ocupacao"] == 0
    assert corpo["items"] == []


# --- Criterio 3 (e item extra 1: TRANSBORDO REAL) ------------------------------
# Tres expedicoes que voltam com mais capturas do que cabe: todos os Pokemon
# entram, e a ocupacao passa da capacidade. Contagem de linhas no banco, nao
# so a resposta HTTP.


def test_tres_expedicoes_resolvidas_transbordam_o_viveiro_e_nenhum_pokemon_se_perde(
    sessao_db, monkeypatch
):
    sessao = _registrar("Criterio3Transbordo")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinadores = _treinadores(sessao)
    livres = _pokemon_livres(sessao)
    assert len(treinadores) == len(livres) == 3

    # Um starter por treinador: o viveiro esvazia ANTES do patch de
    # capacidade, para que o despacho dos tres ainda seja permitido.
    for treinador, pokemon in zip(treinadores, livres, strict=True):
        resposta = _definir_time(sessao, treinador["id"], [pokemon["id"]])
        assert resposta.status_code == 200

    # `app.game.balance` e um modulo so: `expedicoes_service.balance` e
    # `balance` (importado acima) sao o MESMO objeto, entao um patch so basta
    # para a guarda do despacho, para o GET /ranch e para qualquer outro
    # modulo que leia a constante (Artigo IV).
    capacidade_patchada = 2
    monkeypatch.setattr(balance, "CAPACIDADE_VIVEIRO", capacidade_patchada)

    _fixar_semente_expedicao(monkeypatch, SEMENTE_UMA_CAPTURA)
    carga = [{"item_id": "poke-ball", "quantidade": 3}]
    for treinador in treinadores:
        despacho = _despachar(sessao, treinador["id"], carga=carga)
        assert despacho.status_code == 201
        expedicao_id = despacho.json()["id"]
        _forjar_eta_passado_expedicao(sessao_db, expedicao_id)
        relatorio = _claim_expedicao(sessao, expedicao_id)
        assert relatorio.status_code == 200
        capturas = relatorio.json()["relatorio"]["capturas"]
        assert len(capturas) == 1, relatorio.json()  # calibrado pela SEMENTE_UMA_CAPTURA

    corpo = _viveiro(sessao).json()
    assert corpo["ocupacao"] == 3
    assert corpo["transbordado"] is True
    assert corpo["lugares_faltando"] == 3 - capacidade_patchada

    total_no_banco = _contar_pokemon_no_banco(sessao_db, laboratorio_id)
    # 3 starters (um por time) + 3 capturados: nenhum se perdeu no transbordo.
    assert total_no_banco == len(balance.STARTER_SPECIES_IDS) + 3


# --- Criterio 4 ----------------------------------------------------------------
# Viveiro acima da capacidade: despachar e recusado dizendo quantos lugares
# faltam.


def test_despacho_e_recusado_com_viveiro_transbordado_dizendo_quantos_lugares_faltam(
    sessao_db, monkeypatch
):
    sessao = _registrar("Criterio4Despacho")
    treinador_id = _treinadores(sessao)[0]["id"]

    capacidade_patchada = 2
    monkeypatch.setattr(balance, "CAPACIDADE_VIVEIRO", capacidade_patchada)

    resposta = _despachar(sessao, treinador_id)

    assert resposta.status_code == 409
    corpo = resposta.json()
    assert corpo["erro"]["codigo"] == "VIVEIRO_TRANSBORDADO"
    esperado_faltando = len(balance.STARTER_SPECIES_IDS) - capacidade_patchada
    assert corpo["erro"]["detalhes"]["lugares_faltando"] == esperado_faltando


# --- Criterio 5 (e item extra 2: A GUARDA NAO VAZOU) ---------------------------
#
# O teste mais importante do arquivo. Com o viveiro transbordado: despachar e
# recusado, MAS reclamar relatorio, aceitar entrega, concluir entrega e
# soltar continuam funcionando. A guarda escapando para qualquer um destes
# quatro prenderia o professor sem saida.


def test_viveiro_transbordado_bloqueia_so_o_despacho_e_mais_nada(sessao_db, monkeypatch):
    sessao = _registrar("Criterio5GuardaNaoVaza")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinadores = _treinadores(sessao)
    livres = _pokemon_livres(sessao)

    # Um starter em expedicao (para testar "reclamar relatorio" sob
    # transbordo), os outros dois seguem no viveiro.
    treinador_expedicao, treinador_entrega, treinador_sobrando = treinadores
    pokemon_expedicao, pokemon_sobra_a, _pokemon_sobra_b = livres

    resposta = _definir_time(sessao, treinador_expedicao["id"], [pokemon_expedicao["id"]])
    assert resposta.status_code == 200
    _fixar_semente_expedicao(monkeypatch, SEMENTE_UMA_CAPTURA)
    despacho = _despachar(
        sessao,
        treinador_expedicao["id"],
        carga=[{"item_id": "poke-ball", "quantidade": 3}],
    )
    assert despacho.status_code == 201
    expedicao_id = despacho.json()["id"]
    _forjar_eta_passado_expedicao(sessao_db, expedicao_id)

    # Uma entrega atendivel (2 Pidgey), com o estoque de Pidgey ja no viveiro.
    _fixar_gerador_de_entregas(monkeypatch, SEMENTE_PEDIDO_DOIS_PIDGEY)
    lista = _refresh_entregas(sessao)
    assert lista.status_code == 200
    entrega = _pedido_de_dois_pidgey(lista.json()["items"])
    pidgey_ids = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=2)

    # Agora sim: patcha a capacidade para ZERO. Qualquer ocupacao positiva —
    # e sempre havera uma, o laboratorio nunca fica vazio — fica transbordada
    # daqui ate o fim do teste, independente de quantos Pokemon entrarem ou
    # saiam pelos caminhos abaixo.
    monkeypatch.setattr(balance, "CAPACIDADE_VIVEIRO", 0)

    viveiro_antes = _viveiro(sessao).json()
    assert viveiro_antes["transbordado"] is True

    # A porta que FECHA: despachar uma expedicao nova.
    outro_despacho = _despachar(sessao, treinador_sobrando["id"])
    assert outro_despacho.status_code == 409
    assert outro_despacho.json()["erro"]["codigo"] == "VIVEIRO_TRANSBORDADO"

    # As quatro portas que CONTINUAM abertas:

    # 1. Reclamar relatorio.
    relatorio = _claim_expedicao(sessao, expedicao_id)
    assert relatorio.status_code == 200

    # 2. Aceitar entrega.
    aceite = _aceitar_entrega(
        sessao,
        entrega["id"],
        treinador_entrega["id"],
        [str(pid) for pid in pidgey_ids],
    )
    assert aceite.status_code == 200

    # 3. Soltar.
    soltura = _soltar(sessao, pokemon_sobra_a["id"])
    assert soltura.status_code == 204

    # 4. Concluir entrega.
    _forjar_eta_passado_entrega(sessao_db, entrega["id"])
    conclusao = _claim_entrega(sessao, entrega["id"])
    assert conclusao.status_code == 200

    # A porta que fecha continua fechada: o transbordo nao foi resolvido (so
    # diminuido), e o despacho segue recusado.
    ainda_transbordado = _viveiro(sessao).json()
    assert ainda_transbordado["transbordado"] is True
    mais_um_despacho = _despachar(sessao, treinador_sobrando["id"])
    assert mais_um_despacho.status_code == 409
    assert mais_um_despacho.json()["erro"]["codigo"] == "VIVEIRO_TRANSBORDADO"


# --- Criterio 6 ----------------------------------------------------------------
# Soltar um Pokemon do viveiro: ele some e a ocupacao cai em um.


def test_soltar_um_pokemon_do_viveiro_reduz_a_ocupacao_em_um(sessao_db):
    sessao = _registrar("Criterio6Soltar")
    alvo = _pokemon_livres(sessao)[0]
    ocupacao_antes = _viveiro(sessao).json()["ocupacao"]

    resposta = _soltar(sessao, alvo["id"])

    assert resposta.status_code == 204
    corpo = _viveiro(sessao).json()
    assert corpo["ocupacao"] == ocupacao_antes - 1
    assert alvo["id"] not in {item["id"] for item in corpo["items"]}
    assert client.get(f"/pokemon/{alvo['id']}", headers=_cabecalho(sessao)).status_code == 404


# --- Criterio 7 (e item extra 3: SOLTAR NAO PAGA) ------------------------------
# Soltar nao rende nada: o saldo e o estoque ficam exatamente iguais.


def test_soltar_nao_muda_saldo_nem_estoque(sessao_db):
    sessao = _registrar("Criterio7SoltarNaoPaga")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    alvo = _pokemon_livres(sessao)[0]

    moedas_antes = _perfil(sessao)["laboratorio"]["moedas"]
    estoque_antes = _itens_do_laboratorio(sessao_db, laboratorio_id)

    resposta = _soltar(sessao, alvo["id"])
    assert resposta.status_code == 204

    assert _perfil(sessao)["laboratorio"]["moedas"] == moedas_antes
    assert _itens_do_laboratorio(sessao_db, laboratorio_id) == estoque_antes


# --- Criterio 8 ----------------------------------------------------------------
# Soltar do time de um treinador disponivel: o time encolhe.


def test_soltar_do_time_de_treinador_disponivel_encolhe_o_time(sessao_db):
    sessao = _registrar("Criterio8SoltarDoTime")
    treinador_id = _treinadores(sessao)[0]["id"]
    pokemon = _pokemon_livres(sessao)[0]
    assert _definir_time(sessao, treinador_id, [pokemon["id"]]).status_code == 200

    resposta = _soltar(sessao, pokemon["id"])

    assert resposta.status_code == 204
    ficha = _ficha_treinador(sessao, treinador_id)
    assert ficha["time"] == []
    assert ficha["status"] == "DISPONIVEL"


# --- Criterio 9 ----------------------------------------------------------------
# Pokemon em expedicao: soltar e recusado.


def test_soltar_pokemon_em_expedicao_e_recusado(sessao_db, monkeypatch):
    sessao = _registrar("Criterio9EmExpedicao")
    treinador_id = _treinadores(sessao)[0]["id"]
    pokemon = _pokemon_livres(sessao)[0]
    assert _definir_time(sessao, treinador_id, [pokemon["id"]]).status_code == 200
    _fixar_semente_expedicao(monkeypatch, SEMENTE_UMA_CAPTURA)
    assert _despachar(sessao, treinador_id).status_code == 201

    resposta = _soltar(sessao, pokemon["id"])

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "POKEMON_EM_EXPEDICAO"


# --- Criterio 10 ----------------------------------------------------------------
# Pokemon comprometido com entrega: soltar e recusado.


def test_soltar_pokemon_comprometido_com_entrega_e_recusado(sessao_db, monkeypatch):
    sessao = _registrar("Criterio10Comprometido")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinadores(sessao)[0]["id"]

    _fixar_gerador_de_entregas(monkeypatch, SEMENTE_PEDIDO_DOIS_PIDGEY)
    entrega = _pedido_de_dois_pidgey(_refresh_entregas(sessao).json()["items"])
    pidgey_ids = _inserir_pokemon_no_viveiro(sessao_db, laboratorio_id, PIDGEY_ID, quantidade=2)
    aceite = _aceitar_entrega(sessao, entrega["id"], treinador_id, [str(pid) for pid in pidgey_ids])
    assert aceite.status_code == 200

    resposta = _soltar(sessao, str(pidgey_ids[0]))

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "POKEMON_COMPROMETIDO"


# --- Criterio 11 ----------------------------------------------------------------
# O laboratorio nunca fica sem nenhum Pokemon: soltar o ultimo e recusado.


def test_soltar_ultimo_pokemon_do_laboratorio_e_recusado(sessao_db):
    sessao = _registrar("Criterio11UltimoPokemon")
    livres = _pokemon_livres(sessao)
    assert len(livres) == len(balance.STARTER_SPECIES_IDS)

    for pokemon in livres[:-1]:
        assert _soltar(sessao, pokemon["id"]).status_code == 204

    resposta = _soltar(sessao, livres[-1]["id"])

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "ULTIMO_POKEMON"
    # Recusado: a linha continua no banco.
    assert _contar_pokemon_no_banco(sessao_db, uuid.UUID(sessao["laboratorio"]["id"])) == 1


# --- Criterio 12 (e item extra 4: SOLTAR NAO APAGA A POKEDEX) ------------------
# Capturar, soltar, e a Pokedex continua marcando visto e capturado.


def test_soltar_depois_de_capturar_mantem_a_pokedex_vista_e_capturada(sessao_db, monkeypatch):
    sessao = _registrar("Criterio12Pokedex")
    treinador_id = _treinadores(sessao)[0]["id"]
    pokemon = _pokemon_livres(sessao)[0]
    assert _definir_time(sessao, treinador_id, [pokemon["id"]]).status_code == 200

    _fixar_semente_expedicao(monkeypatch, SEMENTE_UMA_CAPTURA)
    despacho = _despachar(sessao, treinador_id, carga=[{"item_id": "poke-ball", "quantidade": 3}])
    assert despacho.status_code == 201
    _forjar_eta_passado_expedicao(sessao_db, despacho.json()["id"])
    relatorio = _claim_expedicao(sessao, despacho.json()["id"]).json()["relatorio"]
    captura = relatorio["capturas"][0]
    especie_id = captura["especie_id"]
    capturado_id = captura["pokemon_id"]

    antes = next(item for item in _pokedex(sessao)["items"] if item["numero"] == especie_id)
    assert antes["estado"] == "CAPTURADA"

    assert _soltar(sessao, capturado_id).status_code == 204

    depois = next(item for item in _pokedex(sessao)["items"] if item["numero"] == especie_id)
    assert depois["estado"] == "CAPTURADA"
    assert depois["nome"] == antes["nome"]


# --- Escopo (item extra 14) ----------------------------------------------------
# Pokemon de outro laboratorio: 404, nunca 403.


def test_soltar_pokemon_de_outro_laboratorio_devolve_404(sessao_db):
    sessao_a = _registrar("Criterio14EscopoA")
    sessao_b = _registrar("Criterio14EscopoB")
    pokemon_de_b = _pokemon_livres(sessao_b)[0]

    resposta = _soltar(sessao_a, pokemon_de_b["id"])

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"
    # Nada mudou no laboratorio de B.
    assert pokemon_de_b["id"] in {p["id"] for p in _pokemon_livres(sessao_b)}
