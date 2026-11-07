"""Contrato de `/expeditions` (spec 006): os catorze criterios de aceite, mais
o que a constituicao exige para qualquer escrita idempotente, qualquer leitura
escopada por laboratorio e qualquer derivacao de estado por relogio.

Cada teste nomeia o comportamento observavel que verifica, nao a forma interna
de `services/expedicoes.py` nem de `repositories/expedicoes.py` (Artigo IX): o
que conta e o que a spec promete ao professor, e por isso os testes passam
pela API HTTP de ponta a ponta, como o cliente a usa — exceto a concorrencia,
que chama o servico direto com uma sessao de banco por thread, mesmo padrao de
`test_trainers.py` e `test_correcoes_revisao.py`, porque compartilhar um unico
`TestClient` entre threads nao e a garantia que esta suite quer testar.

O determinismo de `game/expedition.py` (duas chamadas com o mesmo `agora` e o
mesmo `seed` produzindo o mesmo despacho) ja esta coberto em
`test_game_expedition.py`, no nivel do dominio puro — nao repetido aqui.
"""

from __future__ import annotations

import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.core.config import Settings
from app.core.database import SessionLocal, engine
from app.core.erros import ConflitoDeExpedicao
from app.game import balance
from app.main import app
from app.models import Expedicao, ItemEstoque
from app.repositories.expedicoes import LIMITE_MAXIMO, LIMITE_PADRAO
from app.schemas.expedicoes import ItemDaCargaEntrada
from app.services import expedicoes as expedicoes_service
from tests.conftest import requer_banco

pytestmark = requer_banco

client = TestClient(app)

LOCAL_ALCANCAVEL = "route-1"  # vizinho de pallet-town, alcancavel por qualquer laboratorio novo
LOCAL_FORA_DE_ALCANCE = "cerulean-city"  # exige rota ja desbloqueada (spec 005)
LOCAL_INEXISTENTE = "saffron-city"  # nao faz parte dos dez locais da v1


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


def _treinador_pronto(sessao: dict) -> str:
    """O primeiro treinador do laboratorio, com um Pokemon no time.

    E o minimo que o invariante 17 exige: um treinador sem Pokemon e estado
    valido, mas nao e despachavel.
    """
    treinador_id = _treinadores(sessao)[0]["id"]
    pokemon_id = _pokemon_livres(sessao)[0]["id"]
    resposta = _definir_time(sessao, treinador_id, [pokemon_id])
    assert resposta.status_code == 200
    return treinador_id


def _despachar(sessao: dict, treinador_id: str, local_id: str = LOCAL_ALCANCAVEL, carga=None):
    return client.post(
        "/expeditions",
        json={"treinador_id": treinador_id, "local_id": local_id, "carga": carga or []},
        headers=_cabecalho(sessao),
    )


def _prever(sessao: dict, treinador_id: str, local_id: str = LOCAL_ALCANCAVEL, carga=None):
    return client.post(
        "/expeditions/preview",
        json={"treinador_id": treinador_id, "local_id": local_id, "carga": carga or []},
        headers=_cabecalho(sessao),
    )


def _listar(sessao: dict, status: str | None = None):
    params = {"status": status} if status else {}
    return client.get("/expeditions", params=params, headers=_cabecalho(sessao))


def _obter(sessao: dict, expedicao_id: str):
    return client.get(f"/expeditions/{expedicao_id}", headers=_cabecalho(sessao))


def _abortar(sessao: dict, expedicao_id: str):
    return client.delete(f"/expeditions/{expedicao_id}", headers=_cabecalho(sessao))


def _forjar_eta_passado(sessao_db, expedicao_id: str) -> None:
    """Simula uma expedicao cujo tempo acabou, sem esperar o relogio de verdade."""
    sessao_db.expire_all()
    expedicao = sessao_db.get(Expedicao, uuid.UUID(expedicao_id))
    expedicao.eta = datetime.now(UTC) - timedelta(seconds=1)
    sessao_db.commit()


def _quantidade_em_estoque(sessao_db, laboratorio_id: uuid.UUID, item_id: str) -> int:
    sessao_db.expire_all()
    estoque = sessao_db.get(ItemEstoque, (laboratorio_id, item_id))
    return estoque.quantidade if estoque else 0


def _fake_settings(escala: float):
    """Uma fabrica de `Settings` com a escala escolhida, para substituir
    `get_settings` dentro de `services/expedicoes.py` sem tocar o ambiente de
    verdade nem lutar com o `lru_cache` de `get_settings`."""

    def _fabrica() -> Settings:
        return Settings(_env_file=None, expedition_time_scale=escala)

    return _fabrica


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


# --- Criterio 1 ----------------------------------------------------------------
# Treinador com time e destino alcancavel: a expedicao nasce com previsao de
# retorno e o treinador fica ocupado.


def test_despachar_cria_expedicao_com_previsao_de_retorno_e_ocupa_o_treinador(sessao_db):
    sessao = _registrar("Criterio1")
    treinador_id = _treinador_pronto(sessao)

    resposta = _despachar(sessao, treinador_id)

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["status"] == "EM_CURSO"
    assert corpo["estado_observado"] == "EM_CURSO"
    assert corpo["eta"] > corpo["started_at"]
    assert corpo["segundos_restantes"] > 0
    assert _ficha_treinador(sessao, treinador_id)["status"] == "EM_EXPEDICAO"


# --- Alem dos catorze: semente grande chega como string sem perder digito -----


def test_seed_acima_do_inteiro_seguro_do_js_chega_como_string_sem_perder_digito(
    sessao_db, monkeypatch
):
    """`ExpedicaoResumoLer.seed` e serializado como STRING (revisao da Fase 7,
    achado 2): o Artigo III promete reproducao exata, mas um `number` de JSON
    perde digitos acima de 2**53-1 -- o maior inteiro que o `number` de 64
    bits do JavaScript representa sem arredondar. Uma semente PEQUENA nao
    provaria nada aqui: um `int` cru no corpo tambem bateria digito a digito
    abaixo desse teto, e foi assim que a troca de tipo ficou sem regressao da
    primeira vez. `balance.SEED_MAXIMO` e o proprio teto do sorteio
    (`random.randrange` em `despachar()`), nunca um literal calibrado a mao."""
    semente_grande = balance.SEED_MAXIMO - 1
    assert semente_grande > 2**53 - 1  # premissa do teste

    monkeypatch.setattr(expedicoes_service.random, "randrange", lambda *_args: semente_grande)

    sessao = _registrar("SeedGrandeComoString")
    treinador_id = _treinador_pronto(sessao)

    resposta = _despachar(sessao, treinador_id)
    assert resposta.status_code == 201

    corpo_cru = resposta.json()
    assert isinstance(corpo_cru["seed"], str)
    assert corpo_cru["seed"] == str(semente_grande)
    assert int(corpo_cru["seed"]) == semente_grande

    detalhe_cru = _obter(sessao, corpo_cru["id"]).json()
    assert detalhe_cru["seed"] == str(semente_grande)


# --- Criterio 2 ----------------------------------------------------------------
# Treinador sem Pokemon no time: recusado com o motivo (invariante 17).


def test_treinador_sem_pokemon_no_time_e_recusado_com_motivo(sessao_db):
    sessao = _registrar("Criterio2")
    treinador_id = _treinadores(sessao)[0]["id"]  # sem time definido

    resposta = _despachar(sessao, treinador_id)

    assert resposta.status_code == 409
    corpo = resposta.json()
    assert corpo["erro"]["codigo"] == "TIME_VAZIO"
    assert corpo["erro"]["mensagem"]


# --- Criterio 3 ----------------------------------------------------------------
# Treinador ja em expedicao: a segunda tentativa e recusada.


def test_treinador_ja_em_expedicao_e_recusado_ao_despachar_de_novo(sessao_db):
    sessao = _registrar("Criterio3")
    treinador_id = _treinador_pronto(sessao)
    assert _despachar(sessao, treinador_id).status_code == 201

    segunda = _despachar(sessao, treinador_id)

    assert segunda.status_code == 409
    assert segunda.json()["erro"]["codigo"] == "TREINADOR_OCUPADO"


# --- Criterio 4 ----------------------------------------------------------------
# Destino fora de alcance: recusado.


def test_destino_fora_de_alcance_e_recusado(sessao_db):
    sessao = _registrar("Criterio4")
    treinador_id = _treinador_pronto(sessao)

    resposta = _despachar(sessao, treinador_id, local_id=LOCAL_FORA_DE_ALCANCE)

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "DESTINO_FORA_DE_ALCANCE"


# --- Criterio 5 ----------------------------------------------------------------
# Tres treinadores com time despacham: as tres expedicoes correm ao mesmo tempo.


def test_tres_treinadores_despacham_e_as_tres_expedicoes_correm_simultaneamente(sessao_db):
    sessao = _registrar("Criterio5")
    treinadores = _treinadores(sessao)
    livres = _pokemon_livres(sessao)
    assert len(treinadores) == balance.TREINADORES_NO_KIT_INICIAL == len(livres)

    criadas = []
    for treinador, pokemon in zip(treinadores, livres, strict=True):
        assert _definir_time(sessao, treinador["id"], [pokemon["id"]]).status_code == 200
        resposta = _despachar(sessao, treinador["id"])
        assert resposta.status_code == 201
        criadas.append(resposta.json()["id"])

    ativas = _listar(sessao, status="EM_CURSO").json()
    assert ativas["total"] == len(criadas)
    assert {item["id"] for item in ativas["items"]} == set(criadas)


# --- Criterio 6 ----------------------------------------------------------------
# Com os tres unicos treinadores do laboratorio ocupados, nenhuma quarta
# expedicao parte: nao ha um quarto treinador, e nenhum dos tres livres aceita
# mais de uma missao por vez (regra 7 da spec: o teto e so os livres).


def test_todos_os_treinadores_ocupados_recusa_uma_quarta_expedicao(sessao_db):
    sessao = _registrar("Criterio6")
    treinadores = _treinadores(sessao)
    livres = _pokemon_livres(sessao)
    for treinador, pokemon in zip(treinadores, livres, strict=True):
        _definir_time(sessao, treinador["id"], [pokemon["id"]])
        assert _despachar(sessao, treinador["id"]).status_code == 201

    quarta = _despachar(sessao, treinadores[0]["id"])

    assert quarta.status_code == 409
    assert quarta.json()["erro"]["codigo"] == "TREINADOR_OCUPADO"
    assert _listar(sessao, status="EM_CURSO").json()["total"] == balance.TREINADORES_NO_KIT_INICIAL


# --- Criterio 7 ----------------------------------------------------------------
# Carga de duas Pocoes: o estoque diminui exatamente duas Pocoes.


def test_carga_de_duas_pocoes_debita_duas_pocoes_do_estoque(sessao_db):
    sessao = _registrar("Criterio7")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinador_pronto(sessao)
    antes = _quantidade_em_estoque(sessao_db, laboratorio_id, "potion")

    resposta = _despachar(sessao, treinador_id, carga=[{"item_id": "potion", "quantidade": 2}])

    assert resposta.status_code == 201
    assert _quantidade_em_estoque(sessao_db, laboratorio_id, "potion") == antes - 2


# --- Criterio 8 ----------------------------------------------------------------
# Carga maior que o estoque: recusada, e nada e debitado.


def test_carga_maior_que_o_estoque_e_recusada_e_nada_e_debitado(sessao_db):
    sessao = _registrar("Criterio8")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinador_pronto(sessao)
    estoque_de_pocao = balance.ESTOQUE_INICIAL["potion"]

    resposta = _despachar(
        sessao, treinador_id, carga=[{"item_id": "potion", "quantidade": estoque_de_pocao + 1}]
    )

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "ESTOQUE_INSUFICIENTE"
    assert _quantidade_em_estoque(sessao_db, laboratorio_id, "potion") == estoque_de_pocao


# --- Criterio 9 ----------------------------------------------------------------
# Expedicao em curso: a lista mostra o tempo restante calculado pelo servidor.


def test_lista_mostra_o_tempo_restante_calculado_pelo_servidor(sessao_db):
    sessao = _registrar("Criterio9")
    treinador_id = _treinador_pronto(sessao)
    criada = _despachar(sessao, treinador_id).json()

    listada = next(item for item in _listar(sessao).json()["items"] if item["id"] == criada["id"])

    assert listada["segundos_restantes"] > 0
    assert listada["segundos_restantes"] <= criada["segundos_restantes"]


# --- Criterio 10 ---------------------------------------------------------------
# Recarregar a pagina: o tempo restante continua coerente (nunca sobe).


def test_tempo_restante_continua_coerente_ao_recarregar(sessao_db):
    sessao = _registrar("Criterio10")
    treinador_id = _treinador_pronto(sessao)
    expedicao_id = _despachar(sessao, treinador_id).json()["id"]

    primeira_leitura = _obter(sessao, expedicao_id).json()["segundos_restantes"]
    segunda_leitura = _obter(sessao, expedicao_id).json()["segundos_restantes"]

    assert segunda_leitura <= primeira_leitura
    assert segunda_leitura > 0


# --- Criterio 11 ---------------------------------------------------------------
# Tempo acabado: a expedicao aparece terminada e aguardando o relatorio, sem
# que a coluna gravada tenha mudado (o "estado que ninguem pediu" do plan.md).


def test_expedicao_com_tempo_esgotado_aparece_aguardando_relatorio(sessao_db):
    sessao = _registrar("Criterio11")
    treinador_id = _treinador_pronto(sessao)
    expedicao_id = _despachar(sessao, treinador_id).json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    resposta = _obter(sessao, expedicao_id).json()

    assert resposta["status"] == "EM_CURSO"
    assert resposta["estado_observado"] == "AGUARDANDO_RELATORIO"
    assert resposta["segundos_restantes"] == 0


# --- Criterio 12 ---------------------------------------------------------------
# Abortar: o treinador fica disponivel na hora, e os itens levados nao voltam.


def test_abortar_libera_o_treinador_na_hora_e_nao_devolve_os_itens(sessao_db):
    sessao = _registrar("Criterio12")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinador_pronto(sessao)
    antes = _quantidade_em_estoque(sessao_db, laboratorio_id, "potion")
    expedicao_id = _despachar(
        sessao, treinador_id, carga=[{"item_id": "potion", "quantidade": 1}]
    ).json()["id"]

    resposta = _abortar(sessao, expedicao_id)

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "ABORTADA"
    assert corpo["estado_observado"] == "ABORTADA"
    assert _ficha_treinador(sessao, treinador_id)["status"] == "DISPONIVEL"
    assert _quantidade_em_estoque(sessao_db, laboratorio_id, "potion") == antes - 1


def test_abortar_uma_expedicao_que_ja_terminou_e_recusado(sessao_db):
    """Regra 12: uma expedicao abortada nao produz relatorio nem recompensa.
    Abortar depois que o tempo ja acabou so apagaria a chance de a Fase 7
    resolver — por isso `AGUARDANDO_RELATORIO` recusa o aborto (decisao
    registrada em `ExpedicaoNaoEstaEmCurso`)."""
    sessao = _registrar("Criterio12b")
    treinador_id = _treinador_pronto(sessao)
    expedicao_id = _despachar(sessao, treinador_id).json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    resposta = _abortar(sessao, expedicao_id)

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "EXPEDICAO_NAO_ESTA_EM_CURSO"


# --- Criterio 13 ---------------------------------------------------------------
# Expedicao de outro professor: 404.


def test_expedicao_de_outro_professor_devolve_404(sessao_db):
    sessao_a = _registrar("Criterio13A")
    sessao_b = _registrar("Criterio13B")
    treinador_id = _treinador_pronto(sessao_a)
    expedicao_id = _despachar(sessao_a, treinador_id).json()["id"]

    resposta = _obter(sessao_b, expedicao_id)

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"


# --- Criterio 14 (e item extra 1: concorrencia no treinador, Artigo VII) -------
#
# Despachada duas vezes em paralelo com o mesmo treinador: so uma e criada.
# Threads reais com barreira, sessao de banco propria por thread — mesmo
# padrao de `test_trainers.py` e `test_correcoes_revisao.py`.


def test_despachar_duas_vezes_em_paralelo_com_o_mesmo_treinador_cria_so_uma_expedicao(sessao_db):
    sessao = _registrar("Criterio14")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = uuid.UUID(_treinador_pronto(sessao))

    resultados: list[tuple[str, str | None]] = []
    trava = threading.Lock()
    partida = threading.Barrier(2)

    def despachar() -> None:
        partida.wait()
        with SessionLocal() as sessao_local:
            try:
                expedicoes_service.despachar(
                    sessao_local, laboratorio_id, treinador_id, LOCAL_ALCANCAVEL, []
                )
                with trava:
                    resultados.append(("ok", None))
            except ConflitoDeExpedicao as erro:
                with trava:
                    resultados.append(("erro", erro.codigo))

    threads = [threading.Thread(target=despachar) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    sucessos = [r for r in resultados if r[0] == "ok"]
    falhas = [r for r in resultados if r[0] == "erro"]
    assert len(sucessos) == 1, resultados
    assert len(falhas) == 1, resultados
    assert falhas[0][1] == "TREINADOR_OCUPADO"

    expedicoes_gravadas = sessao_db.scalars(
        select(Expedicao).where(Expedicao.laboratorio_id == laboratorio_id)
    ).all()
    assert len(expedicoes_gravadas) == 1


# --- Alem dos catorze, item 2: concorrencia no estoque -------------------------
#
# Dois treinadores DIFERENTES disputando o ultimo item do estoque: ao final a
# quantidade nao fica negativa e so um dos dois levou o item — exatamente o
# cenario para o qual o debito condicional existe (plan.md, secao 5).


def test_dois_treinadores_disputando_o_ultimo_item_do_estoque_tem_exatamente_um_sucesso(sessao_db):
    sessao = _registrar("ConcorrenciaEstoque")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_a, treinador_b = _treinadores(sessao)[:2]
    livres = _pokemon_livres(sessao)
    _definir_time(sessao, treinador_a["id"], [livres[0]["id"]])
    _definir_time(sessao, treinador_b["id"], [livres[1]["id"]])

    estoque = sessao_db.get(ItemEstoque, (laboratorio_id, "revive"))
    estoque.quantidade = 1
    sessao_db.commit()

    carga = [ItemDaCargaEntrada(item_id="revive", quantidade=1)]
    resultados: list[tuple[str, str | None]] = []
    trava = threading.Lock()
    partida = threading.Barrier(2)

    def despachar(treinador_id: uuid.UUID) -> None:
        partida.wait()
        with SessionLocal() as sessao_local:
            try:
                expedicoes_service.despachar(
                    sessao_local, laboratorio_id, treinador_id, LOCAL_ALCANCAVEL, carga
                )
                with trava:
                    resultados.append(("ok", None))
            except ConflitoDeExpedicao as erro:
                with trava:
                    resultados.append(("erro", erro.codigo))

    threads = [
        threading.Thread(target=despachar, args=(uuid.UUID(treinador_a["id"]),)),
        threading.Thread(target=despachar, args=(uuid.UUID(treinador_b["id"]),)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    sucessos = [r for r in resultados if r[0] == "ok"]
    falhas = [r for r in resultados if r[0] == "erro"]
    assert len(sucessos) == 1, resultados
    assert len(falhas) == 1, resultados
    assert falhas[0][1] == "ESTOQUE_INSUFICIENTE"
    assert _quantidade_em_estoque(sessao_db, laboratorio_id, "revive") == 0


# --- Alem dos catorze, item 3: o relogio ---------------------------------------
#
# A expedicao vira AGUARDANDO_RELATORIO quando o eta passa, sem nenhuma
# escrita no banco: o status gravado na tabela continua EM_CURSO, e e so o
# estado_observado da resposta que muda.


def test_a_coluna_gravada_continua_em_curso_enquanto_o_estado_observado_muda(sessao_db):
    sessao = _registrar("Relogio")
    treinador_id = _treinador_pronto(sessao)
    expedicao_id = _despachar(sessao, treinador_id).json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    resposta = _obter(sessao, expedicao_id).json()
    status_gravado = sessao_db.scalar(
        select(Expedicao.status).where(Expedicao.id == uuid.UUID(expedicao_id))
    )

    assert status_gravado == "EM_CURSO"
    assert resposta["status"] == "EM_CURSO"
    assert resposta["estado_observado"] == "AGUARDANDO_RELATORIO"


# --- Alem dos catorze, item 4: estado derivado num lugar so --------------------


def test_estado_observado_e_o_mesmo_em_get_expeditions_e_em_get_expeditions_id(sessao_db):
    sessao = _registrar("EstadoUnico")
    treinador_id = _treinador_pronto(sessao)
    expedicao_id = _despachar(sessao, treinador_id).json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    detalhe = _obter(sessao, expedicao_id).json()
    da_lista = next(item for item in _listar(sessao).json()["items"] if item["id"] == expedicao_id)

    assert detalhe["estado_observado"] == da_lista["estado_observado"] == "AGUARDANDO_RELATORIO"
    assert detalhe["segundos_restantes"] == da_lista["segundos_restantes"] == 0


# --- Alem dos catorze, item 5: fuso horario ------------------------------------
#
# `started_at`/`eta` saem do Postgres como `timestamptz`; se o driver algum
# dia devolvesse um `datetime` ingenuo, `game.expedition.exigir_instante_com_fuso`
# recusaria com `RelogioSemFuso` antes de qualquer comparacao estourar
# `TypeError` — mas o caminho feliz e esta trava nunca disparar. Este teste
# forca o caminho completo, lendo de volta do banco com uma sessao nova, e
# confirma que a leitura segue ate o fim sem erro nenhum.


def test_datetimes_vindos_do_banco_sao_timezone_aware_e_a_leitura_nao_estoura(sessao_db):
    sessao = _registrar("FusoHorario")
    treinador_id = _treinador_pronto(sessao)
    expedicao_id = _despachar(sessao, treinador_id).json()["id"]

    with SessionLocal() as sessao_nova:
        expedicao = sessao_nova.get(Expedicao, uuid.UUID(expedicao_id))
        assert expedicao.started_at.tzinfo is not None
        assert expedicao.eta.tzinfo is not None

    resposta = _obter(sessao, expedicao_id)

    assert resposta.status_code == 200
    assert resposta.json()["estado_observado"] == "EM_CURSO"


# --- Alem dos catorze, item 6: a escala multiplica -----------------------------
#
# ADR-004: `EXPEDITION_TIME_SCALE` MULTIPLICA a duracao. O documento errou isso
# ("divide") ate a Fase 5; este teste prova, pela API de ponta a ponta, que uma
# escala menor que 1 encurta a expedicao, e nao o contrario.


def test_escala_menor_que_um_encurta_a_duracao_da_expedicao(sessao_db, monkeypatch):
    sessao_tempo_real = _registrar("EscalaTempoReal")
    sessao_acelerada = _registrar("EscalaAcelerada")
    treinador_tempo_real = _treinador_pronto(sessao_tempo_real)
    treinador_acelerado = _treinador_pronto(sessao_acelerada)

    monkeypatch.setattr(expedicoes_service, "get_settings", _fake_settings(1.0))
    duracao_tempo_real = _despachar(sessao_tempo_real, treinador_tempo_real).json()[
        "duracao_minutos"
    ]

    monkeypatch.setattr(expedicoes_service, "get_settings", _fake_settings(0.1))
    duracao_acelerada = _despachar(sessao_acelerada, treinador_acelerado).json()["duracao_minutos"]

    assert duracao_acelerada < duracao_tempo_real


# --- Alem dos catorze, item 7: aborto nao devolve item -------------------------
#
# Ja coberto dentro do criterio 12 (`test_abortar_libera_o_treinador_na_hora_e_
# nao_devolve_os_itens`), que confere o estoque antes e depois do aborto.


# --- Alem dos catorze, item 8: previa e despacho concordam ---------------------


def _cenario_valido(sessao, sessao_db, laboratorio_id, monkeypatch):
    treinador_id = _treinador_pronto(sessao)
    return treinador_id, LOCAL_ALCANCAVEL, [], True, None


def _cenario_time_vazio(sessao, sessao_db, laboratorio_id, monkeypatch):
    treinador_id = _treinadores(sessao)[0]["id"]
    return treinador_id, LOCAL_ALCANCAVEL, [], False, "TIME_VAZIO"


def _cenario_destino_fora_de_alcance(sessao, sessao_db, laboratorio_id, monkeypatch):
    treinador_id = _treinador_pronto(sessao)
    return treinador_id, LOCAL_FORA_DE_ALCANCE, [], False, "DESTINO_FORA_DE_ALCANCE"


def _cenario_estoque_insuficiente(sessao, sessao_db, laboratorio_id, monkeypatch):
    treinador_id = _treinador_pronto(sessao)
    quantidade_acima_do_estoque = balance.ESTOQUE_INICIAL["potion"] + 1
    carga = [{"item_id": "potion", "quantidade": quantidade_acima_do_estoque}]
    return treinador_id, LOCAL_ALCANCAVEL, carga, False, "ESTOQUE_INSUFICIENTE"


def _cenario_treinador_ocupado(sessao, sessao_db, laboratorio_id, monkeypatch):
    treinador_id = _treinador_pronto(sessao)
    assert _despachar(sessao, treinador_id).status_code == 201
    return treinador_id, LOCAL_ALCANCAVEL, [], False, "TREINADOR_OCUPADO"


def _cenario_viveiro_transbordado(sessao, sessao_db, laboratorio_id, monkeypatch):
    """Achado da revisao da Fase 8: sem isto, a previa dizia "pode despachar"
    com o viveiro transbordado, e o despacho recusava logo em seguida — o
    erro no botao que a previa existe para evitar. `CAPACIDADE_VIVEIRO`
    patchada para zero: qualquer ocupacao (os tres iniciais, sempre
    presentes) ja basta para transbordar.
    """
    treinador_id = _treinador_pronto(sessao)
    monkeypatch.setattr(balance, "CAPACIDADE_VIVEIRO", 0)
    return treinador_id, LOCAL_ALCANCAVEL, [], False, "VIVEIRO_TRANSBORDADO"


CENARIOS_DE_DESPACHO = [
    pytest.param(_cenario_valido, id="valido"),
    pytest.param(_cenario_time_vazio, id="time-vazio"),
    pytest.param(_cenario_destino_fora_de_alcance, id="destino-fora-de-alcance"),
    pytest.param(_cenario_estoque_insuficiente, id="estoque-insuficiente"),
    pytest.param(_cenario_treinador_ocupado, id="treinador-ocupado"),
    pytest.param(_cenario_viveiro_transbordado, id="viveiro-transbordado"),
]


@pytest.mark.parametrize("montar_cenario", CENARIOS_DE_DESPACHO)
def test_previa_e_despacho_concordam_no_veredito(sessao_db, monkeypatch, montar_cenario):
    sessao = _registrar(f"cenario-{montar_cenario.__name__}")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id, local_id, carga, valido_esperado, codigo_esperado = montar_cenario(
        sessao, sessao_db, laboratorio_id, monkeypatch
    )

    previa = _prever(sessao, treinador_id, local_id, carga)
    despacho = _despachar(sessao, treinador_id, local_id, carga)

    assert previa.status_code == 200
    assert previa.json()["valido"] is valido_esperado
    if valido_esperado:
        assert despacho.status_code == 201
        assert previa.json()["codigo"] is None
    else:
        assert despacho.status_code == 409
        assert previa.json()["codigo"] == codigo_esperado
        assert despacho.json()["erro"]["codigo"] == codigo_esperado


# --- Alem dos catorze, item 9: o estoque nunca fica negativo -------------------
#
# A disputa concorrente ja prova o caso dificil (quantidade final 0, nunca
# negativa). Este teste cobre o caminho sequencial no limite exato do estoque.


def test_pedir_exatamente_o_total_em_estoque_zera_sem_ficar_negativo(sessao_db):
    sessao = _registrar("EstoqueNoLimite")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinador_pronto(sessao)
    total_em_estoque = balance.ESTOQUE_INICIAL["revive"]

    resposta = _despachar(
        sessao, treinador_id, carga=[{"item_id": "revive", "quantidade": total_em_estoque}]
    )

    assert resposta.status_code == 201
    assert _quantidade_em_estoque(sessao_db, laboratorio_id, "revive") == 0


# --- Alem dos catorze, item 10: escopo em toda rota ----------------------------


def test_expedicao_de_outro_laboratorio_devolve_404_em_get_e_em_delete(sessao_db):
    sessao_a = _registrar("EscopoExpedicaoA")
    sessao_b = _registrar("EscopoExpedicaoB")
    treinador_de_a = _treinador_pronto(sessao_a)
    expedicao_de_a = _despachar(sessao_a, treinador_de_a).json()["id"]

    resposta_get = _obter(sessao_b, expedicao_de_a)
    resposta_delete = _abortar(sessao_b, expedicao_de_a)

    for resposta in (resposta_get, resposta_delete):
        assert resposta.status_code == 404
        assert resposta.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"
    # A expedicao de A continua intacta: o 404 de B nao a tocou.
    assert _obter(sessao_a, expedicao_de_a).json()["estado_observado"] == "EM_CURSO"


def test_treinador_de_outro_laboratorio_devolve_404_no_despacho_e_na_previa(sessao_db):
    sessao_a = _registrar("EscopoTreinadorA")
    sessao_b = _registrar("EscopoTreinadorB")
    treinador_de_a = _treinador_pronto(sessao_a)

    resposta_despacho = _despachar(sessao_b, treinador_de_a)
    resposta_previa = _prever(sessao_b, treinador_de_a)

    for resposta in (resposta_despacho, resposta_previa):
        assert resposta.status_code == 404
        assert resposta.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"


def test_local_inexistente_devolve_404_no_despacho_e_na_previa(sessao_db):
    sessao = _registrar("LocalInexistente")
    treinador_id = _treinador_pronto(sessao)

    resposta_despacho = _despachar(sessao, treinador_id, local_id=LOCAL_INEXISTENTE)
    resposta_previa = _prever(sessao, treinador_id, local_id=LOCAL_INEXISTENTE)

    for resposta in (resposta_despacho, resposta_previa):
        assert resposta.status_code == 404
        assert resposta.json()["erro"]["codigo"] == "LOCAL_DESCONHECIDO"


def test_sem_token_devolve_401_em_toda_rota_de_expedicoes(sessao_db):
    sessao = _registrar("SemToken")
    treinador_id = _treinador_pronto(sessao)
    expedicao_id = _despachar(sessao, treinador_id).json()["id"]

    assert client.get("/expeditions").status_code == 401
    assert client.get(f"/expeditions/{expedicao_id}").status_code == 401
    assert client.post("/expeditions", json={}).status_code == 401
    assert client.post("/expeditions/preview", json={}).status_code == 401
    assert client.delete(f"/expeditions/{expedicao_id}").status_code == 401


# --- Alem dos catorze, item 11: N+1 em GET /expeditions ------------------------


def test_listar_expedicoes_emite_numero_constante_de_consultas(sessao_db):
    sessao_uma = _registrar("NMaisUmA")
    sessao_tres = _registrar("NMaisUmB")

    treinador_unico = _treinador_pronto(sessao_uma)
    assert (
        _despachar(
            sessao_uma, treinador_unico, carga=[{"item_id": "potion", "quantidade": 1}]
        ).status_code
        == 201
    )

    for treinador, pokemon in zip(
        _treinadores(sessao_tres), _pokemon_livres(sessao_tres), strict=True
    ):
        _definir_time(sessao_tres, treinador["id"], [pokemon["id"]])
    for treinador in _treinadores(sessao_tres):
        resposta = _despachar(
            sessao_tres, treinador["id"], carga=[{"item_id": "potion", "quantidade": 1}]
        )
        assert resposta.status_code == 201

    with _contar_consultas() as contagem_uma:
        resposta_uma = client.get("/expeditions", headers=_cabecalho(sessao_uma))
        assert resposta_uma.status_code == 200

    with _contar_consultas() as contagem_tres:
        resposta_tres = client.get("/expeditions", headers=_cabecalho(sessao_tres))
        assert resposta_tres.status_code == 200

    assert len(resposta_uma.json()["items"]) == 1
    assert len(resposta_tres.json()["items"]) == balance.TREINADORES_NO_KIT_INICIAL
    assert contagem_tres["total"] == contagem_uma["total"]


# --- Alem dos catorze: `limite` de GET /expeditions (revisao de mutacao) -------


def test_limite_de_get_expeditions_corta_a_consulta_antes_do_filtro_por_estado(sessao_db):
    """`GET /expeditions` promete "as N mais recentes", nunca "as N mais
    recentes depois de filtrar" (docstring de `repositories.expedicoes.listar`).
    Apagar o `.limit(limite)` da consulta passa a suite inteira em verde --
    nenhum teste ate aqui monta mais historico que `LIMITE_PADRAO`. Cobre o
    padrao, o corte quando se pede menos, o 422 acima do teto (`LIMITE_MAXIMO`,
    nunca um literal), e a regra que surpreende: o corte acontece ANTES do
    filtro por `status`, entao um `limite` pequeno pode fazer uma expedicao
    ABORTADA que existe de verdade no historico nunca aparecer para esse
    filtro, porque a janela cortada nem chega a conte-la."""
    sessao = _registrar("LimiteDeExpedicoes")
    treinador_id = _treinador_pronto(sessao)

    # Historico maior que o padrao, so de expedicoes ABORTADAS.
    total_abortadas = LIMITE_PADRAO + 3
    for _ in range(total_abortadas):
        despacho = _despachar(sessao, treinador_id)
        assert despacho.status_code == 201
        assert _abortar(sessao, despacho.json()["id"]).status_code == 200

    # A ultima expedicao do laboratorio fica ATIVA (nao abortada): e a unica
    # linha de todo o historico que nao e ABORTADA.
    ativa = _despachar(sessao, treinador_id)
    assert ativa.status_code == 201
    assert ativa.json()["estado_observado"] == "EM_CURSO"

    resposta_padrao = client.get("/expeditions", headers=_cabecalho(sessao))
    assert resposta_padrao.status_code == 200
    assert len(resposta_padrao.json()["items"]) == LIMITE_PADRAO

    resposta_cinco = client.get("/expeditions", params={"limite": 5}, headers=_cabecalho(sessao))
    assert resposta_cinco.status_code == 200
    assert len(resposta_cinco.json()["items"]) == 5

    resposta_acima_do_teto = client.get(
        "/expeditions", params={"limite": LIMITE_MAXIMO + 1}, headers=_cabecalho(sessao)
    )
    assert resposta_acima_do_teto.status_code == 422

    # O corte acontece ANTES do filtro: pedindo so a mais recente (que e a
    # ATIVA) e filtrando por ABORTADA, a janela ja cortada nao tem mais
    # nenhuma ABORTADA para o filtro encontrar -- mesmo havendo
    # `total_abortadas` delas no historico completo do laboratorio.
    resposta_corte_antes_do_filtro = client.get(
        "/expeditions",
        params={"limite": 1, "status": "ABORTADA"},
        headers=_cabecalho(sessao),
    )
    assert resposta_corte_antes_do_filtro.status_code == 200
    assert resposta_corte_antes_do_filtro.json()["items"] == []
