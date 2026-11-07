"""Cobertura de `POST /expeditions/{id}/claim` (spec 007, ADR-006).

`game/expedition.py` ja tem a cobertura pura em `test_game_resolucao.py`:
ordem dos sorteios, experiencia, evolucao, captura, cura, tudo isolado de
banco. Este arquivo nao repete nada disso (Artigo IX) -- o que ele cobre e
exatamente o que so aparece atravessando SERVICO, TRANSACAO e HTTP: o lock, a
checagem de status na mesma transacao, a idempotencia, a atomicidade e o
escopo por laboratorio que o Artigo VII exige de toda escrita deste tipo.

A maioria dos testes abaixo verifica um INVARIANTE que vale qualquer que seja
o resultado sorteado (ordem da linha do tempo, corpo identico na releitura,
nada escrito numa recusa, atomicidade, escopo) -- esses despacham com a
semente de verdade, sorteada pelo servico, e por isso continuam validos
qualquer que seja o resultado.

Um punhado de testes (capturas, itens achados, desbloqueio, sucesso vs.
falha) precisa de um resultado ESPECIFICO para ter o que conferir. Forcar um
resultado sem reescrever o sorteio do servico significa forcar a SEMENTE: as
tres constantes `SEMENTE_*` abaixo nao foram adivinhadas, foram encontradas
rodando `app.game.expedition.resolver` diretamente contra o mesmo contexto
que o servico monta para uma expedicao nova a Route 1 -- e o Artigo III
garante que a mesma semente sempre narra a mesma historia, em qualquer
processo, para sempre.
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.database import SessionLocal
from app.game import balance
from app.game import laboratorio as laboratorio_dominio
from app.game import trainers as trainers_dominio
from app.game.expedition import experiencia_de_laboratorio
from app.game.stats import hp_recuperado
from app.main import app
from app.models import (
    Expedicao,
    ExpedicaoEvento,
    ExpedicaoItem,
    Laboratorio,
    Local,
    LocalDesbloqueado,
    PokedexAvistamento,
    PokedexEntrada,
    PokemonInstancia,
    Treinador,
)
from app.repositories.pokemon import ORIGEM_CAPTURADO
from app.services import expedicoes as expedicoes_service
from app.services import relogio
from tests.conftest import requer_banco

pytestmark = requer_banco

client = TestClient(app)

LOCAL_ALCANCAVEL = "route-1"  # vizinho de pallet-town, alcancavel por qualquer laboratorio novo

# Calibradas rodando o dominio puro contra o contexto que o servico monta para
# uma expedicao nova a Route 1 (treinador nivel 1, time de um Pokemon nivel 5 --
# o resultado nao muda entre os tres iniciais nestas tres sementes).
SEMENTE_SUCESSO = 0  # 10 poke-balls, hp 100%: CONCLUIDA_SUCESSO, 1 captura, 0 achados
SEMENTE_SUCESSO_RICA = (
    3  # 10 poke-balls, hp 100%: CONCLUIDA_SUCESSO, 2 capturas, 1 great-ball achado
)
SEMENTE_FALHA = 5  # sem carga, hp 1%: CONCLUIDA_FALHA


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
    """O primeiro treinador do laboratorio, com um Pokemon no time."""
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


def _obter(sessao: dict, expedicao_id: str):
    return client.get(f"/expeditions/{expedicao_id}", headers=_cabecalho(sessao))


def _abortar(sessao: dict, expedicao_id: str):
    return client.delete(f"/expeditions/{expedicao_id}", headers=_cabecalho(sessao))


def _claim(sessao: dict, expedicao_id: str):
    return client.post(f"/expeditions/{expedicao_id}/claim", headers=_cabecalho(sessao))


def _forjar_eta_passado(sessao_db, expedicao_id: str) -> None:
    """Simula uma expedicao cujo tempo acabou, sem esperar o relogio de verdade."""
    sessao_db.expire_all()
    expedicao = sessao_db.get(Expedicao, uuid.UUID(expedicao_id))
    expedicao.eta = datetime.now(UTC) - timedelta(seconds=1)
    sessao_db.commit()


def _quantidade_em_estoque(sessao_db, laboratorio_id: uuid.UUID, item_id: str) -> int:
    from app.models import ItemEstoque

    sessao_db.expire_all()
    estoque = sessao_db.get(ItemEstoque, (laboratorio_id, item_id))
    return estoque.quantidade if estoque else 0


def _forcar_hp(sessao_db, pokemon_id: str, *, pct: int) -> None:
    """Manipula o HP gravado direto no banco, sem passar por nenhuma rota."""
    sessao_db.expire_all()
    pokemon = sessao_db.get(PokemonInstancia, uuid.UUID(pokemon_id))
    pokemon.hp_atual_pct = pct
    sessao_db.commit()


def _forcar_carimbo_de_hp(sessao_db, pokemon_id: str, *, carimbo: datetime) -> None:
    """Manipula `hp_atualizado_em` direto no banco, para simular tempo passado sem dormir."""
    sessao_db.expire_all()
    pokemon = sessao_db.get(PokemonInstancia, uuid.UUID(pokemon_id))
    pokemon.hp_atualizado_em = carimbo
    sessao_db.commit()


def _local_desbloqueado(sessao_db, laboratorio_id: uuid.UUID, local_id: str) -> bool:
    sessao_db.commit()
    sessao_db.expire_all()
    return sessao_db.get(LocalDesbloqueado, (laboratorio_id, local_id)) is not None


def _fixar_semente(monkeypatch, semente: int) -> None:
    """Forca a proxima semente que `despachar()` sorteia (ver docstring do modulo)."""
    monkeypatch.setattr(expedicoes_service.random, "randrange", lambda *_args, s=semente: s)


def _fake_settings(escala: float):
    def _fabrica() -> Settings:
        return Settings(_env_file=None, expedition_time_scale=escala)

    return _fabrica


def _retrato(
    sessao_db, *, laboratorio_id: uuid.UUID, expedicao_id: uuid.UUID, treinador_id: uuid.UUID
):
    """Um retrato comparavel do que a resolucao pode tocar, para o teste 6."""
    from app.models import ItemEstoque

    sessao_db.commit()
    sessao_db.expire_all()

    pokemons = sorted(
        (
            (
                str(p.id),
                p.especie_id,
                p.nivel,
                p.experiencia,
                p.hp_atual_pct,
                p.hp_atualizado_em,
                p.treinador_id,
            )
            for p in sessao_db.scalars(
                select(PokemonInstancia).where(PokemonInstancia.laboratorio_id == laboratorio_id)
            )
        ),
        key=lambda linha: linha[0],
    )
    estoque = sorted(
        (linha.item_id, linha.quantidade)
        for linha in sessao_db.scalars(
            select(ItemEstoque).where(ItemEstoque.laboratorio_id == laboratorio_id)
        )
    )
    treinador = sessao_db.get(Treinador, treinador_id)
    laboratorio = sessao_db.get(Laboratorio, laboratorio_id)
    avistamentos = sorted(
        (a.especie_id, a.local_id, a.vezes_visto)
        for a in sessao_db.scalars(
            select(PokedexAvistamento).where(PokedexAvistamento.laboratorio_id == laboratorio_id)
        )
    )
    total_eventos = sessao_db.scalar(
        select(func.count())
        .select_from(ExpedicaoEvento)
        .where(ExpedicaoEvento.expedicao_id == expedicao_id)
    )
    return {
        "pokemons": pokemons,
        "estoque": estoque,
        "treinador": (
            treinador.nivel,
            treinador.experiencia,
            treinador.status,
            treinador.expedicoes_concluidas,
        ),
        "laboratorio": (laboratorio.nivel, laboratorio.experiencia),
        "avistamentos": avistamentos,
        "total_eventos": total_eventos,
    }


# --- 1: caminho feliz ---------------------------------------------------------


def test_claim_apos_prazo_devolve_linha_do_tempo_completa_de_partida_a_retorno(sessao_db):
    sessao = _registrar("ClaimLinhaDoTempo")
    treinador_id = _treinador_pronto(sessao)
    expedicao_id = _despachar(sessao, treinador_id).json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    resposta = _claim(sessao, expedicao_id)

    assert resposta.status_code == 200
    corpo = resposta.json()
    relatorio = corpo["relatorio"]
    eventos = relatorio["eventos"]
    assert eventos[0]["tipo"] == "PARTIDA"
    assert eventos[-1]["tipo"] == "RETORNO"
    assert [evento["ordem"] for evento in eventos] == list(range(len(eventos)))
    assert corpo["expedicao"]["status"] in ("CONCLUIDA_SUCESSO", "CONCLUIDA_FALHA")
    assert corpo["expedicao"]["status"] == corpo["expedicao"]["estado_observado"]
    assert relatorio["status"] == corpo["expedicao"]["status"]


# --- 1b: cada evento gravado tem texto, minuto e payload de verdade (mutacao) --


def test_eventos_gravados_tem_texto_minuto_e_payload_coerentes_com_o_tipo(sessao_db, monkeypatch):
    """`gravar_eventos` so tinha guarda para `ordem` e `tipo` -- `texto=""`,
    `ocorrido_em_minuto=0` ou `payload=None`, gravados no lugar do que
    `EventoDeCampo` de fato carregava, passavam a suite inteira em verde.
    Confere por uma releitura de `ExpedicaoEvento` direto do banco (sessao
    DIFERENTE da que o `claim` escreveu): todo evento tem texto nao vazio; o
    ultimo (`RETORNO`, regra 1) acontece no minuto da duracao contratada, nao
    no minuto zero da partida; e todo `BATALHA`/`CONTRATEMPO` -- os unicos
    tipos garantidos a existir numa expedicao com pelo menos um encontro
    (regra 4) -- carrega no payload a especie que de fato foi enfrentada."""
    sessao = _registrar("EventosGravadosComDados")
    treinador_id = _treinador_pronto(sessao)

    _fixar_semente(monkeypatch, SEMENTE_SUCESSO)
    despacho = _despachar(sessao, treinador_id, carga=[{"item_id": "poke-ball", "quantidade": 3}])
    assert despacho.status_code == 201
    expedicao_id = despacho.json()["id"]
    duracao_minutos = despacho.json()["duracao_minutos"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    resposta = _claim(sessao, expedicao_id)
    assert resposta.status_code == 200
    # Semente calibrada para sucesso (regra 1 e docstring das constantes
    # SEMENTE_*): o retorno acontece no fim da duracao contratada, nunca no
    # minuto zero da partida -- sem isto `duracao_minutos` podia ser zero por
    # acidente e a comparacao abaixo nao provaria nada.
    assert duracao_minutos > 0

    sessao_db.commit()
    sessao_db.expire_all()
    eventos_gravados = sessao_db.scalars(
        select(ExpedicaoEvento)
        .where(ExpedicaoEvento.expedicao_id == uuid.UUID(expedicao_id))
        .order_by(ExpedicaoEvento.ordem)
    ).all()

    assert len(eventos_gravados) >= 2  # ao menos PARTIDA e RETORNO
    assert eventos_gravados[0].tipo == "PARTIDA"
    assert eventos_gravados[-1].tipo == "RETORNO"
    assert eventos_gravados[-1].ocorrido_em_minuto == duracao_minutos

    encontros_com_especie = 0
    for evento in eventos_gravados:
        assert evento.texto.strip() != ""
        assert 0 <= evento.ocorrido_em_minuto <= duracao_minutos
        if evento.tipo in ("BATALHA", "CONTRATEMPO"):
            encontros_com_especie += 1
            assert evento.payload is not None
            assert isinstance(evento.payload.get("especie_id"), int)
            assert evento.payload.get("especie_nome")

    # Regra 4: ao menos um encontro acontece sempre -- sem isto o laco acima
    # podia passar vazio, por acidente.
    assert encontros_com_especie >= 1


# --- 2: claim antes do prazo ---------------------------------------------------


def test_claim_antes_do_prazo_e_recusado_com_409_e_nada_e_escrito(sessao_db):
    sessao = _registrar("ClaimAntesDoPrazo")
    treinador_id = _treinador_pronto(sessao)
    expedicao_id = _despachar(sessao, treinador_id).json()["id"]

    resposta = _claim(sessao, expedicao_id)

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "EXPEDICAO_EM_CURSO"

    sessao_db.commit()
    sessao_db.expire_all()
    expedicao = sessao_db.get(Expedicao, uuid.UUID(expedicao_id))
    assert expedicao.status == "EM_CURSO"
    assert expedicao.resolvida_em is None
    assert expedicao.relatorio_resumo is None
    total_eventos = sessao_db.scalar(
        select(func.count())
        .select_from(ExpedicaoEvento)
        .where(ExpedicaoEvento.expedicao_id == expedicao.id)
    )
    assert total_eventos == 0
    treinador = sessao_db.get(Treinador, uuid.UUID(treinador_id))
    assert treinador.status == "EM_EXPEDICAO"


# --- 3: claim de expedicao abortada --------------------------------------------


def test_claim_de_expedicao_abortada_e_recusado_com_409(sessao_db):
    sessao = _registrar("ClaimAbortada")
    treinador_id = _treinador_pronto(sessao)
    expedicao_id = _despachar(sessao, treinador_id).json()["id"]
    assert _abortar(sessao, expedicao_id).status_code == 200

    resposta = _claim(sessao, expedicao_id)

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "EXPEDICAO_ABORTADA"


# --- 4: escopo ------------------------------------------------------------------


def test_claim_de_expedicao_de_outro_laboratorio_devolve_404(sessao_db):
    sessao_a = _registrar("ClaimEscopoA")
    sessao_b = _registrar("ClaimEscopoB")
    treinador_a = _treinador_pronto(sessao_a)
    expedicao_id = _despachar(sessao_a, treinador_a).json()["id"]

    resposta = _claim(sessao_b, expedicao_id)

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"


# --- 5 e 6: idempotencia --------------------------------------------------------


def test_segundo_claim_devolve_o_mesmo_corpo_byte_a_byte(sessao_db):
    sessao = _registrar("ClaimIdempotenteCorpo")
    treinador_id = _treinador_pronto(sessao)
    expedicao_id = _despachar(sessao, treinador_id).json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    primeira = _claim(sessao, expedicao_id)
    segunda = _claim(sessao, expedicao_id)

    assert primeira.status_code == segunda.status_code == 200
    assert primeira.content == segunda.content
    assert primeira.json() == segunda.json()


def test_segundo_claim_nao_muda_nenhuma_linha_do_banco(sessao_db):
    sessao = _registrar("ClaimIdempotenteBanco")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = uuid.UUID(_treinador_pronto(sessao))
    expedicao_id = _despachar(sessao, str(treinador_id)).json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)
    assert _claim(sessao, expedicao_id).status_code == 200

    antes = _retrato(
        sessao_db,
        laboratorio_id=laboratorio_id,
        expedicao_id=uuid.UUID(expedicao_id),
        treinador_id=treinador_id,
    )

    assert _claim(sessao, expedicao_id).status_code == 200

    depois = _retrato(
        sessao_db,
        laboratorio_id=laboratorio_id,
        expedicao_id=uuid.UUID(expedicao_id),
        treinador_id=treinador_id,
    )

    assert depois == antes


# --- 7: concorrencia na mesma expedicao (Artigo VII) ---------------------------


def test_duas_chamadas_concorrentes_de_claim_na_mesma_expedicao_resolvem_uma_unica_vez(sessao_db):
    sessao = _registrar("ClaimConcorrente")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = uuid.UUID(_treinador_pronto(sessao))
    despacho = _despachar(
        sessao, str(treinador_id), carga=[{"item_id": "poke-ball", "quantidade": 10}]
    )
    assert despacho.status_code == 201
    expedicao_id = uuid.UUID(despacho.json()["id"])
    # Estoque de CADA item que a tabela de achados pode sortear (balance.py),
    # ANTES do claim: alguns (potion, revive) ja tem estoque inicial nao-zero,
    # entao "a soma aconteceu uma unica vez" so se prova contra esta base, nao
    # contra zero.
    estoque_antes = {
        item_id: _quantidade_em_estoque(sessao_db, laboratorio_id, item_id)
        for item_id, _peso in balance.TABELA_DE_ACHADOS
    }
    _forjar_eta_passado(sessao_db, str(expedicao_id))

    resultados = []
    trava = threading.Lock()
    partida = threading.Barrier(2)

    def resolver() -> None:
        partida.wait()
        with SessionLocal() as sessao_local:
            corpo = expedicoes_service.claim(sessao_local, laboratorio_id, expedicao_id)
            with trava:
                resultados.append(corpo)

    threads = [threading.Thread(target=resolver) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(resultados) == 2
    relatorio_a, relatorio_b = (corpo.relatorio for corpo in resultados)
    assert relatorio_a.model_dump() == relatorio_b.model_dump()

    sessao_db.commit()
    sessao_db.expire_all()

    total_eventos = sessao_db.scalar(
        select(func.count())
        .select_from(ExpedicaoEvento)
        .where(ExpedicaoEvento.expedicao_id == expedicao_id)
    )
    assert total_eventos == len(relatorio_a.eventos)
    ordens = sorted(
        sessao_db.scalars(
            select(ExpedicaoEvento.ordem).where(ExpedicaoEvento.expedicao_id == expedicao_id)
        )
    )
    assert ordens == list(range(len(relatorio_a.eventos)))

    capturas_no_banco = sessao_db.scalars(
        select(PokemonInstancia).where(
            PokemonInstancia.laboratorio_id == laboratorio_id,
            PokemonInstancia.origem == ORIGEM_CAPTURADO,
        )
    ).all()
    assert len(capturas_no_banco) == len(relatorio_a.capturas)

    treinador = sessao_db.get(Treinador, treinador_id)
    assert treinador.expedicoes_concluidas == 1
    assert treinador.status == "DISPONIVEL"

    for item in relatorio_a.itens_encontrados:
        assert (
            _quantidade_em_estoque(sessao_db, laboratorio_id, item.item_id)
            == estoque_antes[item.item_id] + item.quantidade
        )


# --- 8: concorrencia entre expedicoes do mesmo laboratorio (regressao) --------


def test_tres_claims_concorrentes_de_expedicoes_diferentes_somam_a_experiencia_do_laboratorio(
    sessao_db, monkeypatch
):
    """Regressao do achado de `laboratorios_repo.travar` sem `populate_existing`:
    sem a correcao, so a ultima escrita das tres vencia e as outras duas
    experiencias eram jogadas fora em silencio -- este teste falhava antes
    dela."""
    sessao = _registrar("TresClaimsMesmoLab")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinadores = _treinadores(sessao)
    livres = _pokemon_livres(sessao)
    assert len(treinadores) == balance.TREINADORES_NO_KIT_INICIAL == len(livres)

    _fixar_semente(monkeypatch, SEMENTE_SUCESSO)
    expedicao_ids = []
    for treinador, pokemon in zip(treinadores, livres, strict=True):
        assert _definir_time(sessao, treinador["id"], [pokemon["id"]]).status_code == 200
        # Quantidade 3, nao 10: os tres treinadores dividem o MESMO estoque de
        # 10 poke-balls do laboratorio (balance.ESTOQUE_INICIAL), e a semente
        # calibrada so precisa de 2 para capturar (ver comentario das
        # constantes `SEMENTE_*` no topo do arquivo).
        despacho = _despachar(
            sessao, treinador["id"], carga=[{"item_id": "poke-ball", "quantidade": 3}]
        )
        assert despacho.status_code == 201
        expedicao_id = despacho.json()["id"]
        _forjar_eta_passado(sessao_db, expedicao_id)
        expedicao_ids.append(uuid.UUID(expedicao_id))

    sessao_db.commit()
    sessao_db.expire_all()
    experiencia_antes = sessao_db.get(Laboratorio, laboratorio_id).experiencia

    resultados = []
    trava = threading.Lock()
    partida = threading.Barrier(3)

    def resolver(expedicao_id: uuid.UUID) -> None:
        with SessionLocal() as sessao_local:
            # Precondicao do bug (ver docstring): em producao TODA rota
            # autenticada passa por `professor_atual`, que ja carregou este
            # `Laboratorio` na sessao da requisicao ANTES de qualquer lock --
            # e mantem uma referencia FORTE a ele em `SessaoProfessor` durante
            # a requisicao inteira. A identity map do SQLAlchemy e fraca: sem
            # guardar o retorno de `get()` em uma variavel viva ate o fim desta
            # funcao, o objeto perderia toda referencia, o coletor de lixo o
            # apagaria do identity map, e o `claim()` abaixo encontraria a
            # sessao "limpa" -- exatamente como os outros testes deste
            # arquivo, que chamam o servico direto sem essa precondicao, e
            # por isso nunca pegam este bug.
            laboratorio_pre_carregado = sessao_local.get(Laboratorio, laboratorio_id)
            assert laboratorio_pre_carregado is not None
            partida.wait()
            corpo = expedicoes_service.claim(sessao_local, laboratorio_id, expedicao_id)
            with trava:
                resultados.append(corpo)
            # Mantem a variavel viva ate aqui: qualquer coisa antes disso e
            # especulacao sobre quando o GC rodaria.
            del laboratorio_pre_carregado

    threads = [
        threading.Thread(target=resolver, args=(expedicao_id,)) for expedicao_id in expedicao_ids
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(resultados) == 3
    ganhos = [corpo.relatorio.laboratorio.exp_ganha for corpo in resultados]
    # Semente calibrada para sucesso: as tres expedicoes rendem experiencia.
    assert all(ganho > 0 for ganho in ganhos), [corpo.relatorio.status for corpo in resultados]

    sessao_db.commit()
    sessao_db.expire_all()
    experiencia_depois = sessao_db.get(Laboratorio, laboratorio_id).experiencia
    assert experiencia_depois == experiencia_antes + sum(ganhos)


# --- 14: o laboratorio SOBE DE NIVEL ao cruzar o limiar (revisao de mutacao) ---


def test_laboratorio_sobe_de_nivel_quando_a_experiencia_cruza_o_limiar(sessao_db, monkeypatch):
    """Regra 15 e criterio 14 nao prometem so experiencia: prometem NIVEL. Uma
    mutacao que troca `nivel_laboratorio_depois` pelo nivel ANTIGO do
    laboratorio passa limpa em qualquer teste que compare o nivel gravado
    contra `relatorio.laboratorio` -- os dois lados mudam juntos. Aqui o
    laboratorio e montado a uma experiencia a UM ponto do limiar do nivel 2
    (lido de `game.laboratorio.experiencia_total_para_nivel`, nunca um
    literal), a expedicao resolve com sucesso garantido, e o nivel ESPERADO e
    recalculado pela mesma formula do dominio a partir do ganho que o
    relatorio de fato anunciou -- nunca contra `relatorio.laboratorio` em si."""
    sessao = _registrar("LaboratorioSobeDeNivel")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinador_pronto(sessao)

    limiar_nivel_2 = laboratorio_dominio.experiencia_total_para_nivel(2)
    sessao_db.expire_all()
    laboratorio = sessao_db.get(Laboratorio, laboratorio_id)
    laboratorio.experiencia = limiar_nivel_2 - 1
    laboratorio.nivel = laboratorio_dominio.nivel_para_experiencia(limiar_nivel_2 - 1)
    sessao_db.commit()
    assert laboratorio.nivel == 1  # premissa do teste: ainda nivel 1, a 1 de distancia

    local_destino = sessao_db.get(Local, LOCAL_ALCANCAVEL)
    nivel_dificuldade = local_destino.nivel_dificuldade

    _fixar_semente(monkeypatch, SEMENTE_SUCESSO)
    despacho = _despachar(sessao, treinador_id, carga=[{"item_id": "poke-ball", "quantidade": 3}])
    assert despacho.status_code == 201
    expedicao_id = despacho.json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    resposta = _claim(sessao, expedicao_id)
    assert resposta.status_code == 200
    ganho = resposta.json()["relatorio"]["laboratorio"]["exp_ganha"]
    # So o sucesso paga (regra 15): o ganho bate com a formula do dominio
    # aplicada a dificuldade do destino, nao com um numero adivinhado.
    assert ganho == experiencia_de_laboratorio(nivel_dificuldade)

    experiencia_esperada = (limiar_nivel_2 - 1) + ganho
    nivel_esperado = laboratorio_dominio.nivel_para_experiencia(experiencia_esperada)
    # Sem isto o teste podia passar por o limiar nao ser de fato cruzado.
    assert nivel_esperado >= 2

    sessao_db.commit()
    sessao_db.expire_all()
    laboratorio_db = sessao_db.get(Laboratorio, laboratorio_id)
    assert laboratorio_db.experiencia == experiencia_esperada
    assert laboratorio_db.nivel == nivel_esperado


# --- 9: efeito no mundo -- capturas ---------------------------------------------


def test_capturas_vao_para_o_laboratorio_soltas_e_o_time_do_treinador_nao_muda(
    sessao_db, monkeypatch
):
    sessao = _registrar("CapturasSoltas")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinador_pronto(sessao)
    tamanho_do_time_antes = len(_ficha_treinador(sessao, treinador_id)["time"])

    _fixar_semente(monkeypatch, SEMENTE_SUCESSO_RICA)
    despacho = _despachar(sessao, treinador_id, carga=[{"item_id": "poke-ball", "quantidade": 10}])
    assert despacho.status_code == 201
    expedicao_id = despacho.json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    resposta = _claim(sessao, expedicao_id)
    assert resposta.status_code == 200
    capturas = resposta.json()["relatorio"]["capturas"]
    assert len(capturas) > 0  # calibrado pela SEMENTE_SUCESSO_RICA

    sessao_db.commit()
    sessao_db.expire_all()
    for captura in capturas:
        pokemon = sessao_db.get(PokemonInstancia, uuid.UUID(captura["pokemon_id"]))
        assert pokemon.laboratorio_id == laboratorio_id
        assert pokemon.treinador_id is None
        assert pokemon.origem == ORIGEM_CAPTURADO
        assert pokemon.nivel == captura["nivel"]

    assert len(_ficha_treinador(sessao, treinador_id)["time"]) == tamanho_do_time_antes


# --- 10: itens consumidos e achados ---------------------------------------------


def test_itens_consumidos_saem_da_carga_sem_debitar_o_estoque_de_novo_e_achados_somam(
    sessao_db, monkeypatch
):
    sessao = _registrar("ItensDoRelatorio")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinador_pronto(sessao)

    _fixar_semente(monkeypatch, SEMENTE_SUCESSO_RICA)
    despacho = _despachar(sessao, treinador_id, carga=[{"item_id": "poke-ball", "quantidade": 10}])
    assert despacho.status_code == 201
    expedicao_id = despacho.json()["id"]

    poke_ball_apos_despacho = _quantidade_em_estoque(sessao_db, laboratorio_id, "poke-ball")
    great_ball_apos_despacho = _quantidade_em_estoque(sessao_db, laboratorio_id, "great-ball")

    _forjar_eta_passado(sessao_db, expedicao_id)
    resposta = _claim(sessao, expedicao_id)
    assert resposta.status_code == 200
    relatorio = resposta.json()["relatorio"]
    consumidos = {item["item_id"]: item["quantidade"] for item in relatorio["itens_consumidos"]}
    achados = {item["item_id"]: item["quantidade"] for item in relatorio["itens_encontrados"]}
    # Calibrado pela SEMENTE_SUCESSO_RICA: consome poke-ball tentando capturar,
    # acha great-ball -- um item de cada tipo, para os dois numeros nao se
    # confundirem.
    assert consumidos.get("poke-ball", 0) > 0
    assert achados.get("great-ball", 0) > 0

    assert _quantidade_em_estoque(sessao_db, laboratorio_id, "poke-ball") == poke_ball_apos_despacho
    assert (
        _quantidade_em_estoque(sessao_db, laboratorio_id, "great-ball")
        == great_ball_apos_despacho + achados["great-ball"]
    )


# --- 11: desbloqueio de destino --------------------------------------------------


def test_desbloqueio_de_destino_so_em_sucesso_e_idempotente_entre_expedicoes(
    sessao_db, monkeypatch
):
    sessao = _registrar("Desbloqueio")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinadores = _treinadores(sessao)
    livres = _pokemon_livres(sessao)
    assert len(treinadores) == balance.TREINADORES_NO_KIT_INICIAL == len(livres)

    # Primeiro treinador: expedicao fadada ao fracasso (hp quase zero) -- uma
    # FALHA nao pode desbloquear o destino.
    treinador_falha, pokemon_falha = treinadores[0], livres[0]
    assert _definir_time(sessao, treinador_falha["id"], [pokemon_falha["id"]]).status_code == 200
    _forcar_hp(sessao_db, pokemon_falha["id"], pct=1)
    _fixar_semente(monkeypatch, SEMENTE_FALHA)
    despacho_falha = _despachar(sessao, treinador_falha["id"])
    assert despacho_falha.status_code == 201
    expedicao_falha = despacho_falha.json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_falha)
    claim_falha = _claim(sessao, expedicao_falha)
    assert claim_falha.status_code == 200
    assert claim_falha.json()["relatorio"]["status"] == "CONCLUIDA_FALHA"
    assert claim_falha.json()["relatorio"]["local_desbloqueado"] is False
    assert _local_desbloqueado(sessao_db, laboratorio_id, LOCAL_ALCANCAVEL) is False

    # Segundo treinador: expedicao calibrada para sucesso -- agora desbloqueia.
    treinador_a, pokemon_a = treinadores[1], livres[1]
    assert _definir_time(sessao, treinador_a["id"], [pokemon_a["id"]]).status_code == 200
    _fixar_semente(monkeypatch, SEMENTE_SUCESSO)
    despacho_a = _despachar(
        sessao, treinador_a["id"], carga=[{"item_id": "poke-ball", "quantidade": 3}]
    )
    assert despacho_a.status_code == 201
    expedicao_a = despacho_a.json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_a)
    claim_a = _claim(sessao, expedicao_a)
    assert claim_a.status_code == 200
    assert claim_a.json()["relatorio"]["status"] == "CONCLUIDA_SUCESSO"
    assert claim_a.json()["relatorio"]["local_desbloqueado"] is True
    assert _local_desbloqueado(sessao_db, laboratorio_id, LOCAL_ALCANCAVEL) is True

    # Terceiro treinador: mesmo destino, tambem sucesso -- ja estava aberto.
    treinador_b, pokemon_b = treinadores[2], livres[2]
    assert _definir_time(sessao, treinador_b["id"], [pokemon_b["id"]]).status_code == 200
    _fixar_semente(monkeypatch, SEMENTE_SUCESSO)
    despacho_b = _despachar(
        sessao, treinador_b["id"], carga=[{"item_id": "poke-ball", "quantidade": 3}]
    )
    assert despacho_b.status_code == 201
    expedicao_b = despacho_b.json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_b)
    claim_b = _claim(sessao, expedicao_b)
    assert claim_b.status_code == 200
    assert claim_b.json()["relatorio"]["status"] == "CONCLUIDA_SUCESSO"
    assert claim_b.json()["relatorio"]["local_desbloqueado"] is False

    sessao_db.commit()
    sessao_db.expire_all()
    linhas = sessao_db.scalars(
        select(LocalDesbloqueado).where(
            LocalDesbloqueado.laboratorio_id == laboratorio_id,
            LocalDesbloqueado.local_id == LOCAL_ALCANCAVEL,
        )
    ).all()
    assert len(linhas) == 1


# --- 12: avistamento soma, nao duplica linha ------------------------------------


def test_avistamento_da_mesma_especie_no_mesmo_local_soma_sem_duplicar_linha(sessao_db):
    sessao = _registrar("AvistamentoSoma")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinadores = _treinadores(sessao)
    livres = _pokemon_livres(sessao)

    total_encontros = 0
    for treinador, pokemon in zip(treinadores[:2], livres[:2], strict=True):
        assert _definir_time(sessao, treinador["id"], [pokemon["id"]]).status_code == 200
        despacho = _despachar(sessao, treinador["id"])
        assert despacho.status_code == 201
        expedicao_id = despacho.json()["id"]
        _forjar_eta_passado(sessao_db, expedicao_id)
        resposta = _claim(sessao, expedicao_id)
        assert resposta.status_code == 200
        total_encontros += resposta.json()["relatorio"]["encontros"]

    sessao_db.commit()
    sessao_db.expire_all()
    avistamentos = sessao_db.scalars(
        select(PokedexAvistamento).where(
            PokedexAvistamento.laboratorio_id == laboratorio_id,
            PokedexAvistamento.local_id == LOCAL_ALCANCAVEL,
        )
    ).all()

    # Route 1 so tem duas especies no seed (data/seed/encounters.json): mesmo
    # apos duas expedicoes, no maximo duas linhas -- nunca uma por encontro.
    assert len(avistamentos) <= 2
    assert sum(linha.vezes_visto for linha in avistamentos) == total_encontros


# --- 13: atomicidade (Artigo VII) -----------------------------------------------


def test_erro_no_meio_da_gravacao_nao_deixa_nada_pela_metade(sessao_db, monkeypatch):
    sessao = _registrar("Atomicidade")
    treinador_id = _treinador_pronto(sessao)
    despacho = _despachar(sessao, treinador_id)
    assert despacho.status_code == 201
    expedicao_id = despacho.json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    def _quebrar(*_args, **_kwargs):
        raise RuntimeError("falha forcada para o teste de atomicidade (Artigo VII)")

    with monkeypatch.context() as remendo:
        remendo.setattr(expedicoes_service.pokedex_repo, "registrar_avistamentos", _quebrar)
        with pytest.raises(RuntimeError):
            _claim(sessao, expedicao_id)

    sessao_db.commit()
    sessao_db.expire_all()
    expedicao = sessao_db.get(Expedicao, uuid.UUID(expedicao_id))
    assert expedicao.status == "EM_CURSO"
    assert expedicao.resolvida_em is None
    assert expedicao.relatorio_resumo is None
    total_eventos = sessao_db.scalar(
        select(func.count())
        .select_from(ExpedicaoEvento)
        .where(ExpedicaoEvento.expedicao_id == expedicao.id)
    )
    assert total_eventos == 0
    treinador = sessao_db.get(Treinador, uuid.UUID(treinador_id))
    assert treinador.status == "EM_EXPEDICAO"

    # Reclamavel depois, sem a quebra: o claim vermelho nao corrompeu nada.
    resposta = _claim(sessao, expedicao_id)
    assert resposta.status_code == 200
    assert resposta.json()["relatorio"]["status"] in ("CONCLUIDA_SUCESSO", "CONCLUIDA_FALHA")


# --- 14: GET nao escreve (ADR-006) ----------------------------------------------


def test_consultar_expedicao_vencida_cem_vezes_nao_resolve_nada(sessao_db):
    sessao = _registrar("GetNaoEscreve")
    treinador_id = _treinador_pronto(sessao)
    expedicao_id = _despachar(sessao, treinador_id).json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    for _ in range(100):
        resposta = _obter(sessao, expedicao_id)
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo["status"] == "EM_CURSO"
        assert corpo["estado_observado"] == "AGUARDANDO_RELATORIO"
        assert corpo["relatorio"] is None

    sessao_db.commit()
    sessao_db.expire_all()
    expedicao = sessao_db.get(Expedicao, uuid.UUID(expedicao_id))
    assert expedicao.status == "EM_CURSO"
    assert expedicao.resolvida_em is None


# --- 15: recuperacao passiva, relogio.py (sem cobertura ate aqui) --------------


_INSTANTE = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def test_minutos_de_jogo_com_escala_um_conta_os_minutos_reais_direto():
    agora = _INSTANTE + timedelta(minutes=12, seconds=59)
    assert relogio.minutos_de_jogo(_INSTANTE, agora, escala=1.0) == 12


def test_minutos_de_jogo_com_escala_pequena_multiplica_o_tempo_de_jogo():
    agora = _INSTANTE + timedelta(seconds=6)  # 0,1 minuto real
    assert relogio.minutos_de_jogo(_INSTANTE, agora, escala=0.01) == 10


def test_minutos_de_jogo_com_relogio_andando_para_tras_devolve_zero():
    agora = _INSTANTE - timedelta(minutes=5)
    assert relogio.minutos_de_jogo(_INSTANTE, agora, escala=1.0) == 0


def test_minutos_de_jogo_com_escala_zero_ou_negativa_devolve_zero():
    agora = _INSTANTE + timedelta(minutes=50)
    assert relogio.minutos_de_jogo(_INSTANTE, agora, escala=0.0) == 0
    assert relogio.minutos_de_jogo(_INSTANTE, agora, escala=-1.0) == 0


def test_hp_observado_soma_pontos_conforme_minutos_por_ponto_de_hp():
    minutos = balance.MINUTOS_POR_PONTO_DE_HP * 3
    agora = _INSTANTE + timedelta(minutes=minutos)
    esperado = hp_recuperado(50, minutos)
    assert relogio.hp_observado(50, _INSTANTE, agora=agora, escala=1.0) == esperado
    assert esperado > 50


def test_hp_observado_nunca_passa_de_cem():
    agora = _INSTANTE + timedelta(days=10)
    assert relogio.hp_observado(90, _INSTANTE, agora=agora, escala=1.0) == 100


def test_hp_observado_com_relogio_para_tras_nao_reduz_o_hp():
    agora = _INSTANTE - timedelta(minutes=30)
    assert relogio.hp_observado(40, _INSTANTE, agora=agora, escala=1.0) == 40


# --- 16: recuperacao passiva no laboratorio, nunca em campo (criterios 20/21) --


def test_pokemon_machucado_no_laboratorio_recupera_com_o_tempo_mas_em_expedicao_nao(
    sessao_db, monkeypatch
):
    monkeypatch.setattr("app.services.pokemon.get_settings", _fake_settings(1.0))
    sessao = _registrar("RecuperacaoPassiva")
    livres = _pokemon_livres(sessao)
    pokemon_no_laboratorio, pokemon_em_expedicao = livres[0]["id"], livres[1]["id"]
    treinador_id = _treinadores(sessao)[0]["id"]
    assert _definir_time(sessao, treinador_id, [pokemon_em_expedicao]).status_code == 200

    minutos_passados = balance.MINUTOS_POR_PONTO_DE_HP * 10
    carimbo_antigo = datetime.now(UTC) - timedelta(minutes=minutos_passados)

    _forcar_hp(sessao_db, pokemon_no_laboratorio, pct=50)
    _forcar_carimbo_de_hp(sessao_db, pokemon_no_laboratorio, carimbo=carimbo_antigo)

    _forcar_hp(sessao_db, pokemon_em_expedicao, pct=50)
    assert _despachar(sessao, treinador_id).status_code == 201

    # O MESMO carimbo antigo, aplicado DEPOIS do despacho: se a enfermaria nao
    # parasse em campo (invariante 18), esta leitura creditaria de uma vez so
    # toda a recuperacao que o carimbo manipulado sugere.
    _forcar_carimbo_de_hp(sessao_db, pokemon_em_expedicao, carimbo=carimbo_antigo)

    esperado_no_laboratorio = hp_recuperado(50, minutos_passados)
    assert esperado_no_laboratorio > 50

    ficha_laboratorio = client.get(
        f"/pokemon/{pokemon_no_laboratorio}", headers=_cabecalho(sessao)
    ).json()
    ficha_em_campo = client.get(
        f"/pokemon/{pokemon_em_expedicao}", headers=_cabecalho(sessao)
    ).json()

    assert ficha_laboratorio["hp_atual_pct"] == esperado_no_laboratorio
    assert ficha_em_campo["hp_atual_pct"] == 50


# --- 20b: o HP derivado e o mesmo em TODA rota que devolve Pokemon (mutacao) ---


def test_hp_derivado_bate_na_listagem_de_pokemon_e_no_time_do_treinador(sessao_db, monkeypatch):
    """O plan.md promete `hp_atual_pct` DERIVADO "em toda rota que devolve
    Pokemon" -- so a ficha individual (teste acima) tinha cobertura. Devolver
    o HP CRU em `services/trainers._hp_observado` OU em `services/pokemon.listar`
    passa a suite inteira em verde sem isto. Confere que `GET /pokemon`
    (listagem) e o `time` de `GET /trainers/{id}` mostram o MESMO numero
    derivado que a ficha individual do mesmo Pokemon, nunca o `hp_atual_pct`
    gravado cru."""
    monkeypatch.setattr("app.services.pokemon.get_settings", _fake_settings(1.0))
    monkeypatch.setattr("app.services.trainers.get_settings", _fake_settings(1.0))

    sessao = _registrar("HpDerivadoEmTodaRota")
    treinador_id = _treinador_pronto(sessao)
    pokemon_id = _ficha_treinador(sessao, treinador_id)["time"][0]["id"]

    minutos_passados = balance.MINUTOS_POR_PONTO_DE_HP * 10
    carimbo_antigo = datetime.now(UTC) - timedelta(minutes=minutos_passados)
    _forcar_hp(sessao_db, pokemon_id, pct=50)
    _forcar_carimbo_de_hp(sessao_db, pokemon_id, carimbo=carimbo_antigo)

    esperado = hp_recuperado(50, minutos_passados)
    # Precisa ser DERIVADO de verdade: nem o cru (50) nem so saturado em 100,
    # senao um esquecimento parcial da derivacao passaria pela mesma asserção.
    assert 50 < esperado < 100

    ficha = client.get(f"/pokemon/{pokemon_id}", headers=_cabecalho(sessao)).json()
    assert ficha["hp_atual_pct"] == esperado

    listagem = client.get("/pokemon", headers=_cabecalho(sessao)).json()["items"]
    item_na_listagem = next(item for item in listagem if item["id"] == pokemon_id)
    assert item_na_listagem["hp_atual_pct"] == esperado

    ficha_treinador = _ficha_treinador(sessao, treinador_id)
    membro_no_time = next(m for m in ficha_treinador["time"] if m["id"] == pokemon_id)
    assert membro_no_time["hp_atual_pct"] == esperado

    treinador_na_listagem = next(t for t in _treinadores(sessao) if t["id"] == treinador_id)
    membro_na_listagem_de_treinadores = next(
        m for m in treinador_na_listagem["time"] if m["id"] == pokemon_id
    )
    assert membro_na_listagem_de_treinadores["hp_atual_pct"] == esperado


# --- 17: aborto nao credita o tempo de campo de uma vez (regressao) ------------


def test_abortar_carimba_o_relogio_para_nao_creditar_o_tempo_de_campo_de_uma_vez(
    sessao_db, monkeypatch
):
    """Regressao do achado 2 da revisao da Fase 7: sem `abortar()` recarimbar
    `hp_atualizado_em` do time que volta, a primeira leitura apos o aborto
    creditava de uma vez todo o tempo de relogio que a expedicao levou, como
    se o time tivesse ficado parado na enfermaria o tempo todo."""
    monkeypatch.setattr("app.services.pokemon.get_settings", _fake_settings(1.0))
    sessao = _registrar("AbortarCarimbo")
    treinador_id = _treinador_pronto(sessao)
    pokemon_id = _ficha_treinador(sessao, treinador_id)["time"][0]["id"]

    _forcar_hp(sessao_db, pokemon_id, pct=50)
    expedicao_id = _despachar(sessao, treinador_id).json()["id"]

    muito_tempo_atras = datetime.now(UTC) - timedelta(
        minutes=balance.MINUTOS_POR_PONTO_DE_HP * 1000
    )
    _forcar_carimbo_de_hp(sessao_db, pokemon_id, carimbo=muito_tempo_atras)

    assert _abortar(sessao, expedicao_id).status_code == 200

    ficha = client.get(f"/pokemon/{pokemon_id}", headers=_cabecalho(sessao)).json()
    assert ficha["hp_atual_pct"] == 50


# --- 18: o Pokemon gravado bate com o relatorio (revisao de mutacao) -----------


def test_pokemon_gravado_apos_claim_bate_com_cada_campo_do_relatorio(sessao_db, monkeypatch):
    """O relatorio e o retrato do que a resolucao GRAVOU (regra 3 e criterios
    10 a 12) -- conferir `relatorio.time` contra ele mesmo nao prova que o
    Pokemon do banco mudou. Esta releitura usa `sessao_db`, uma conexao
    diferente da que `claim()` usou para escrever, e confere nivel,
    experiencia, especie (evoluiu ou nao) e o carimbo de HP contra o que o
    relatorio anunciou."""
    sessao = _registrar("PokemonGravadoBateComRelatorio")
    treinador_id = _treinador_pronto(sessao)
    pokemon_id = _ficha_treinador(sessao, treinador_id)["time"][0]["id"]
    ficha_antes = client.get(f"/pokemon/{pokemon_id}", headers=_cabecalho(sessao)).json()
    experiencia_antes = ficha_antes["experiencia"]

    _fixar_semente(monkeypatch, SEMENTE_SUCESSO)
    despacho = _despachar(sessao, treinador_id, carga=[{"item_id": "poke-ball", "quantidade": 3}])
    assert despacho.status_code == 201
    expedicao_id = despacho.json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    resposta = _claim(sessao, expedicao_id)
    assert resposta.status_code == 200
    relatorio = resposta.json()["relatorio"]
    membro = next(item for item in relatorio["time"] if item["pokemon_id"] == pokemon_id)
    # Semente calibrada para sucesso: o time venceu pelo menos uma batalha, e
    # uma vitoria sempre distribui experiencia (regra 7) -- sem isto a
    # comparacao abaixo poderia passar mesmo gravando lixo, se por acaso nada
    # tivesse mudado.
    assert membro["exp_ganha"] > 0

    sessao_db.commit()
    sessao_db.expire_all()
    pokemon = sessao_db.get(PokemonInstancia, uuid.UUID(pokemon_id))
    especie_esperada = membro["evoluiu_para_id"] or membro["especie_id"]
    assert pokemon.especie_id == especie_esperada
    assert pokemon.nivel == membro["nivel_depois"]
    assert pokemon.experiencia == experiencia_antes + membro["exp_ganha"]
    assert pokemon.hp_atual_pct == membro["hp_depois_pct"]
    resolvida_em = datetime.fromisoformat(relatorio["resolvida_em"].replace("Z", "+00:00"))
    assert pokemon.hp_atualizado_em == resolvida_em


# --- 19: nivel e experiencia do treinador gravados batem com o relatorio -------


def test_nivel_e_experiencia_do_treinador_gravados_batem_com_o_relatorio_e_sao_maior_que_zero(
    sessao_db, monkeypatch
):
    """Regra 7 e 20: uma vitoria da um terco da experiencia da batalha ao
    treinador, e a resolucao libera o treinador gravando a progressao que
    `game.trainers` calculou. Confere o valor GRAVADO (releitura por
    `sessao_db`) contra o relatorio, e exige exp_ganha > 0 para que a
    comparacao nao passe por acidente com um relatorio vazio."""
    sessao = _registrar("TreinadorGravadoBateComRelatorio")
    treinador_id = _treinador_pronto(sessao)
    ficha_antes = _ficha_treinador(sessao, treinador_id)
    nivel_antes, experiencia_antes = ficha_antes["nivel"], ficha_antes["experiencia"]

    _fixar_semente(monkeypatch, SEMENTE_SUCESSO)
    despacho = _despachar(sessao, treinador_id, carga=[{"item_id": "poke-ball", "quantidade": 3}])
    assert despacho.status_code == 201
    expedicao_id = despacho.json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    resposta = _claim(sessao, expedicao_id)
    assert resposta.status_code == 200
    ganho = resposta.json()["relatorio"]["treinador"]
    assert ganho["exp_ganha"] > 0
    assert ganho["nivel_antes"] == nivel_antes

    sessao_db.commit()
    sessao_db.expire_all()
    treinador = sessao_db.get(Treinador, uuid.UUID(treinador_id))
    assert treinador.experiencia == experiencia_antes + ganho["exp_ganha"]
    assert treinador.nivel == ganho["nivel_depois"]
    assert treinador.status == "DISPONIVEL"
    assert treinador.expedicoes_concluidas == 1


# --- 19b: o treinador SOBE DE NIVEL ao cruzar o limiar (revisao de mutacao) ----


def test_treinador_sobe_de_nivel_quando_a_experiencia_cruza_o_limiar(sessao_db, monkeypatch):
    """`treinador.nivel == ganho["nivel_depois"]` (teste acima) e tautologico:
    uma mutacao que troca `nivel_treinador_depois` pelo nivel ANTIGO do
    treinador muda os dois lados dessa igualdade juntos -- o relatorio passa a
    anunciar o nivel velho, e o banco grava o nivel velho, e os dois
    continuam batendo. Aqui o treinador e montado a um ponto do limiar do
    nivel 2 (lido de `game.trainers.experiencia_total_para_nivel`, nunca um
    literal) e o nivel ESPERADO e recalculado pela mesma formula do dominio a
    partir do ganho que o proprio relatorio anunciou, nunca contra
    `ganho["nivel_depois"]`."""
    sessao = _registrar("TreinadorSobeDeNivel")
    treinador_id = _treinador_pronto(sessao)

    limiar_nivel_2 = trainers_dominio.experiencia_total_para_nivel(2)
    sessao_db.expire_all()
    treinador = sessao_db.get(Treinador, uuid.UUID(treinador_id))
    treinador.experiencia = limiar_nivel_2 - 1
    treinador.nivel = trainers_dominio.nivel_para_experiencia(limiar_nivel_2 - 1)
    sessao_db.commit()
    assert treinador.nivel == 1  # premissa do teste: ainda nivel 1, a 1 de distancia

    _fixar_semente(monkeypatch, SEMENTE_SUCESSO)
    despacho = _despachar(sessao, treinador_id, carga=[{"item_id": "poke-ball", "quantidade": 3}])
    assert despacho.status_code == 201
    expedicao_id = despacho.json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    resposta = _claim(sessao, expedicao_id)
    assert resposta.status_code == 200
    ganho = resposta.json()["relatorio"]["treinador"]["exp_ganha"]
    # Regra 7: uma vitoria sempre da experiencia ao treinador -- sem isto o
    # teste podia passar com ganho zero, sem o limiar ter sido cruzado.
    assert ganho > 0

    experiencia_esperada = (limiar_nivel_2 - 1) + ganho
    nivel_esperado = trainers_dominio.nivel_para_experiencia(experiencia_esperada)
    assert nivel_esperado >= 2

    sessao_db.commit()
    sessao_db.expire_all()
    treinador_db = sessao_db.get(Treinador, uuid.UUID(treinador_id))
    assert treinador_db.experiencia == experiencia_esperada
    assert treinador_db.nivel == nivel_esperado


# --- 20: Pokedex (visto/capturado) bate com quem foi enfrentado e capturado ----


def test_pokedex_entrada_marca_visto_para_todo_enfrentado_e_capturado_so_para_quem_foi_pego(
    sessao_db, monkeypatch
):
    """Regra 12: toda especie enfrentada entra na Pokedex como vista, e so como
    capturada se foi de fato pega nesta expedicao. `registrar_avistamentos`
    faz DOIS upserts por especie -- `PokedexAvistamento` (contagem por local,
    ja coberta pelo teste 12 deste arquivo) e `PokedexEntrada` (visto/
    capturado, sem cobertura ate aqui: um teste que so contasse linhas de
    `pokedex_avistamentos` nao pegaria o UPSERT de `PokedexEntrada` sumindo)."""
    sessao = _registrar("PokedexEntradaVistoCapturado")
    laboratorio_id = uuid.UUID(sessao["laboratorio"]["id"])
    treinador_id = _treinador_pronto(sessao)

    _fixar_semente(monkeypatch, SEMENTE_SUCESSO_RICA)
    despacho = _despachar(sessao, treinador_id, carga=[{"item_id": "poke-ball", "quantidade": 10}])
    assert despacho.status_code == 201
    expedicao_id = despacho.json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    resposta = _claim(sessao, expedicao_id)
    assert resposta.status_code == 200
    relatorio = resposta.json()["relatorio"]
    especies_vistas = relatorio["especies_vistas"]
    especies_capturadas = {captura["especie_id"] for captura in relatorio["capturas"]}
    # Calibrado pela SEMENTE_SUCESSO_RICA: ha pelo menos uma especie enfrentada
    # e pelo menos uma captura, para os dois ramos (visto-mas-nao-capturado e
    # visto-e-capturado) terem o que provar.
    assert len(especies_vistas) > 0
    assert len(especies_capturadas) > 0

    sessao_db.commit()
    sessao_db.expire_all()
    for especie in especies_vistas:
        entrada = sessao_db.get(PokedexEntrada, (laboratorio_id, especie["especie_id"]))
        assert entrada is not None
        assert entrada.visto is True
        assert entrada.capturado == (especie["especie_id"] in especies_capturadas)


# --- 21: consumo de itens gravado bate com o relatorio e com a ficha -----------


def test_consumo_de_itens_gravado_bate_com_o_relatorio_e_com_a_ficha_da_expedicao(
    sessao_db, monkeypatch
):
    """Regra 17: o que foi consumido em campo sai da CARGA da expedicao
    (`expedicao_itens.quantidade_consumida`), nunca do estoque do laboratorio.
    Confere o valor gravado contra o relatorio do `claim` e contra o que
    `GET /expeditions/{id}` devolve depois -- dois numeros contraditorios na
    mesma tela e exatamente o sintoma que o jogador veria se o UPDATE virasse
    no-op. Confere tambem que um item LEVADO e NAO consumido grava zero, nao
    nulo nem o valor levado."""
    sessao = _registrar("ConsumoDeItensGravado")
    treinador_id = _treinador_pronto(sessao)

    _fixar_semente(monkeypatch, SEMENTE_SUCESSO_RICA)
    despacho = _despachar(
        sessao,
        treinador_id,
        carga=[
            {"item_id": "poke-ball", "quantidade": 10},
            {"item_id": "potion", "quantidade": 5},
        ],
    )
    assert despacho.status_code == 201
    expedicao_id = despacho.json()["id"]
    _forjar_eta_passado(sessao_db, expedicao_id)

    resposta = _claim(sessao, expedicao_id)
    assert resposta.status_code == 200
    relatorio = resposta.json()["relatorio"]
    consumidos = {item["item_id"]: item["quantidade"] for item in relatorio["itens_consumidos"]}
    # Calibrado pela SEMENTE_SUCESSO_RICA (ver constantes no topo do arquivo):
    # consome poke-ball tentando capturar. A Potion foi levada e nunca
    # precisou ser usada -- sem derrota nesta semente -- entao e o caso de
    # "levado e nao consumido" que a regra 17 exige gravar como zero.
    assert consumidos.get("poke-ball", 0) > 0
    assert "potion" not in consumidos or consumidos["potion"] == 0

    sessao_db.commit()
    sessao_db.expire_all()
    item_poke_ball = sessao_db.get(ExpedicaoItem, (uuid.UUID(expedicao_id), "poke-ball"))
    item_potion = sessao_db.get(ExpedicaoItem, (uuid.UUID(expedicao_id), "potion"))
    assert item_poke_ball.quantidade_consumida == consumidos["poke-ball"]
    assert item_potion.quantidade_consumida == 0

    ficha = _obter(sessao, expedicao_id).json()
    carga_por_item = {item["item_id"]: item["quantidade_consumida"] for item in ficha["carga"]}
    assert carga_por_item["poke-ball"] == item_poke_ball.quantidade_consumida
    assert carga_por_item["potion"] == 0
