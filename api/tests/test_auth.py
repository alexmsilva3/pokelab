"""Cobertura dos onze criterios de aceite de specs/002-credenciais-do-professor/spec.md.

Cada teste refere o numero do criterio que verifica, na ordem do spec.md. Os
seis itens extra exigidos pela constituicao (concorrencia, escopo, vazamento
de senha, enumeracao de usuario, atomicidade e idempotencia do kit) aparecem
ao final, onde nao coincidem com um criterio numerado.

Este arquivo testa comportamento observavel pela API (Artigo IX): nenhuma
asserção aqui depende de como `services/auth.py` ou `repositories/` estao
organizados por dentro.
"""

from __future__ import annotations

import threading
import time
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import select

from app.core.config import get_settings
from app.core.erros import ErroDeAplicacao, RecursoNaoEncontrado
from app.core.seguranca import ALGORITMO_TOKEN
from app.game import balance
from app.main import app, tratar_erro_de_aplicacao
from app.models import PokemonInstancia, Professor
from app.repositories import professores as professores_repo
from tests.conftest import requer_banco

pytestmark = requer_banco

client = TestClient(app)


# --- Criterio 1 --------------------------------------------------------------


def test_registro_com_usuario_livre_cria_conta_laboratorio_e_kit_completo(sessao_db):
    """Dado nenhum cadastro, quando o professor se registra com um usuario
    livre, entao existem uma conta, um laboratorio nivel 1 com zero moedas,
    tres Pokemon nivel 5, os treinadores iniciais nivel 1, o estoque e Pallet
    Town desbloqueada."""
    resposta = client.post("/auth/register", json={"usuario": "Ivysaur", "senha": "bulbassauro1"})

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["professor"]["usuario"] == "Ivysaur"
    assert corpo["laboratorio"]["nivel"] == 1
    assert corpo["laboratorio"]["moedas"] == 0

    perfil = client.get("/me", headers={"Authorization": f"Bearer {corpo['token']}"})
    resumo = perfil.json()["resumo"]
    assert resumo["pokemon"] == 3
    assert resumo["treinadores"] == balance.TREINADORES_NO_KIT_INICIAL
    assert resumo["locais_desbloqueados"] == 1
    assert resumo["especies_capturadas"] == 3
    # Tarefa 9 da spec 008: o kit inicial solta os tres no viveiro, nenhum
    # em time ainda, entao a ocupacao do resumo bate com o total.
    assert resumo["ocupacao_viveiro"] == 3


# --- Criterio 2 --------------------------------------------------------------


def test_registro_com_usuario_ja_cadastrado_em_qualquer_caixa_e_recusado(sessao_db):
    """Dado um usuario ja cadastrado, quando alguem tenta registrar o mesmo
    nome em qualquer combinacao de maiusculas, entao a operacao e recusada
    com mensagem clara e nada e criado."""
    client.post("/auth/register", json={"usuario": "Venusaur", "senha": "primeirasenha1"})

    antes = sessao_db.scalar(select(Professor).where(Professor.usuario_normalizado == "venusaur"))
    assert antes is not None

    resposta = client.post("/auth/register", json={"usuario": "VENUSAUR", "senha": "outrasenha12"})

    assert resposta.status_code == 409
    assert resposta.json()["erro"]["codigo"] == "USUARIO_EM_USO"
    assert resposta.json()["erro"]["mensagem"]

    professores = sessao_db.scalars(
        select(Professor).where(Professor.usuario_normalizado == "venusaur")
    ).all()
    assert len(professores) == 1


# --- Criterio 3 --------------------------------------------------------------


def test_registro_com_senha_curta_e_recusado_e_nada_e_criado(sessao_db):
    """Dada uma senha com menos de 8 caracteres, quando se tenta registrar,
    entao a operacao e recusada e nada e criado."""
    resposta = client.post("/auth/register", json={"usuario": "Charizard", "senha": "curta12"})

    assert resposta.status_code == 422
    assert professores_repo.buscar_por_usuario(sessao_db, "Charizard") is None


# --- Criterio 4 --------------------------------------------------------------


def test_login_com_credenciais_corretas_devolve_token(sessao_db):
    """Dadas credenciais corretas, quando o professor entra, entao recebe um
    token de sessao."""
    client.post("/auth/register", json={"usuario": "Blastoise", "senha": "carapaca12345"})

    resposta = client.post("/auth/login", json={"usuario": "Blastoise", "senha": "carapaca12345"})

    assert resposta.status_code == 200
    assert isinstance(resposta.json()["token"], str)
    assert resposta.json()["token"]


# --- Criterio 5 (e item 4 da constituicao: enumeracao de usuario) -----------


def test_login_com_senha_errada_e_com_usuario_inexistente_recusam_de_forma_identica(sessao_db):
    """Dada uma senha errada, quando o professor tenta entrar, entao a
    recusa e identica a de um usuario inexistente -- em codigo, corpo e
    envelope, para que o tempo e a resposta nao denunciem qual dos dois
    casos aconteceu."""
    client.post("/auth/register", json={"usuario": "Pidgeot", "senha": "voeialto12345"})

    senha_errada = client.post(
        "/auth/login", json={"usuario": "Pidgeot", "senha": "senha-errada-123"}
    )
    usuario_inexistente = client.post(
        "/auth/login", json={"usuario": "ninguem-cadastrado-aqui", "senha": "qualquer-coisa-123"}
    )

    assert senha_errada.status_code == usuario_inexistente.status_code == 401
    assert senha_errada.json() == usuario_inexistente.json()
    assert senha_errada.headers.get("content-length") == usuario_inexistente.headers.get(
        "content-length"
    )


# --- Criterio 6 --------------------------------------------------------------


def test_perfil_com_token_valido_devolve_professor_e_laboratorio_sem_campo_de_senha(sessao_db):
    """Dado um token valido, quando o professor consulta seu perfil, entao
    recebe os dados dele e do laboratorio, e nenhum campo de senha."""
    registro = client.post("/auth/register", json={"usuario": "Alakazam", "senha": "colherada123"})
    token = registro.json()["token"]

    resposta = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["professor"]["usuario"] == "Alakazam"
    assert corpo["laboratorio"]["nome"]
    assert "senha" not in corpo["professor"]
    assert "senha_hash" not in corpo["professor"]


# --- Criterio 7 --------------------------------------------------------------


def test_rota_protegida_sem_token_devolve_401(sessao_db):
    """Dada a ausencia de token, quando se chama uma rota protegida, entao
    a resposta e 401."""
    resposta = client.get("/me")
    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "NAO_AUTENTICADO"


def test_rota_protegida_com_token_invalido_devolve_401(sessao_db):
    """Dado um token invalido, quando se chama uma rota protegida, entao a
    resposta e 401."""
    resposta = client.get("/me", headers={"Authorization": "Bearer isto-nao-e-um-jwt"})
    assert resposta.status_code == 401


def test_rota_protegida_com_token_expirado_devolve_401(sessao_db):
    """Dado um token expirado, quando se chama uma rota protegida, entao a
    resposta e 401."""
    settings = get_settings()
    token_expirado = jwt.encode(
        {"sub": str(uuid.uuid4()), "exp": time.time() - 10},
        settings.secret_key,
        algorithm=ALGORITMO_TOKEN,
    )
    resposta = client.get("/me", headers={"Authorization": f"Bearer {token_expirado}"})
    assert resposta.status_code == 401


# --- Criterio 8 (e item 2 da constituicao: escopo) --------------------------


def test_perfil_de_um_professor_nunca_devolve_dados_do_laboratorio_de_outro(sessao_db):
    """Defesa em profundidade da regra 12 com a unica rota protegida que
    esta fase expoe: GET /me nao recebe id nenhum, e mesmo assim precisa
    resolver sempre o laboratorio do dono do token, nunca o de outro
    professor registrado no mesmo banco."""
    professor_a = client.post("/auth/register", json={"usuario": "Onix", "senha": "pedrapedra12"})
    professor_b = client.post("/auth/register", json={"usuario": "Geodude", "senha": "pedrinha123"})

    token_b = professor_b.json()["token"]
    laboratorio_a_id = professor_a.json()["laboratorio"]["id"]

    perfil_b = client.get("/me", headers={"Authorization": f"Bearer {token_b}"})

    assert perfil_b.json()["laboratorio"]["id"] != laboratorio_a_id
    assert perfil_b.json()["laboratorio"]["id"] == professor_b.json()["laboratorio"]["id"]


def test_recurso_nao_encontrado_produz_o_envelope_404_padrao_quando_levantado():
    """O mecanismo do criterio 8 ("pedir um recurso que pertence a outro
    professor responde como se nao existisse") ja esta pronto em
    `app.core.erros.RecursoNaoEncontrado` e cabeado no handler de
    `app.main`, mesmo sem uma rota desta fase que o dispare de ponta a
    ponta (veja o teste pulado abaixo). Este teste confirma que o handler
    real de `app.main` traduz a excecao para o envelope certo, montando uma
    rota descartavel num app de teste -- sem tocar no app de producao.
    """
    app_de_teste = FastAPI()
    app_de_teste.add_exception_handler(ErroDeAplicacao, tratar_erro_de_aplicacao)

    @app_de_teste.get("/recurso-de-outro-laboratorio")
    def _levantar() -> None:
        raise RecursoNaoEncontrado()

    resposta = TestClient(app_de_teste).get("/recurso-de-outro-laboratorio")

    assert resposta.status_code == 404
    assert resposta.json() == {
        "erro": {
            "codigo": "RECURSO_NAO_ENCONTRADO",
            "mensagem": "O recurso solicitado nao existe.",
            "detalhes": None,
        }
    }


def test_acessar_pelo_id_um_recurso_que_pertence_a_outro_professor_responde_404(sessao_db):
    """Criterio de aceite 8 da spec 002, destravado pela Fase 3: `GET /pokemon/{id}`
    e a primeira rota que recebe um recurso por id. O mecanismo generico ja estava
    testado acima; este teste confere a rota real de ponta a ponta.
    """
    dono = client.post("/auth/register", json={"usuario": "Misty", "senha": "starmie12345"})
    outro = client.post("/auth/register", json={"usuario": "Brock", "senha": "onix1234567"})

    pokemon_do_dono = sessao_db.scalars(
        select(PokemonInstancia).where(
            PokemonInstancia.laboratorio_id == dono.json()["laboratorio"]["id"]
        )
    ).first()

    resposta = client.get(
        f"/pokemon/{pokemon_do_dono.id}",
        headers={"Authorization": f"Bearer {outro.json()['token']}"},
    )

    assert resposta.status_code == 404
    assert resposta.json()["erro"]["codigo"] == "RECURSO_NAO_ENCONTRADO"


# --- Criterio 9 (e item 1 da constituicao: concorrencia) --------------------


def test_registro_disparado_duas_vezes_em_paralelo_cria_uma_unica_conta_e_um_unico_kit(
    sessao_db,
):
    """Dado um registro, quando a criacao e disparada duas vezes em
    paralelo com o mesmo usuario, entao apenas uma conta existe ao final e
    o kit foi concedido uma unica vez.

    Cada thread usa o proprio `TestClient`/sessao de banco: a disputa real
    acontece na constraint unica de `usuario_normalizado`, nao em memoria.
    """
    respostas: list = []
    trava = threading.Lock()

    def disparar() -> None:
        resposta = TestClient(app).post(
            "/auth/register", json={"usuario": "Dragonite", "senha": "escama-laranja1"}
        )
        with trava:
            respostas.append(resposta)

    threads = [threading.Thread(target=disparar) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    sucessos = [r for r in respostas if r.status_code == 201]
    falhas = [r for r in respostas if r.status_code == 409]
    assert len(sucessos) == 1
    assert len(falhas) == 4

    professores = sessao_db.scalars(
        select(Professor).where(Professor.usuario_normalizado == "dragonite")
    ).all()
    assert len(professores) == 1

    laboratorio_id = sucessos[0].json()["laboratorio"]["id"]
    pokemon = sessao_db.scalars(
        select(PokemonInstancia).where(PokemonInstancia.laboratorio_id == laboratorio_id)
    ).all()
    assert len(pokemon) == 3


# --- Criterio 10 -------------------------------------------------------------


def test_token_continua_autorizando_apos_varias_chamadas_simulando_recarregar_a_pagina(
    sessao_db,
):
    """Dado um professor autenticado no navegador, quando a pagina e
    recarregada, entao ele continua dentro sem precisar entrar de novo: o
    mesmo token, usado de novo, continua autorizando e devolve o mesmo
    perfil."""
    registro = client.post("/auth/register", json={"usuario": "Mewtwo", "senha": "psiquico12345"})
    token = registro.json()["token"]

    primeira_visita = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    segunda_visita = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert primeira_visita.status_code == segunda_visita.status_code == 200
    assert primeira_visita.json() == segunda_visita.json()


# --- Criterio 11 (e item 3 da constituicao: vazamento de senha) -------------


def _coletar_rotas_da_aplicacao():
    """Rotas de verdade registradas no app (APIRoute), ignorando docs/openapi.

    Caminha recursivamente para lidar tanto com a lista plana de rotas
    quanto com o wrapper que versoes mais novas do FastAPI usam para
    roteadores incluidos via `include_router` -- assim o teste continua
    generico mesmo que a estrutura interna do FastAPI mude de novo.
    """
    rotas = []

    def visitar(iteravel):
        for item in iteravel:
            if hasattr(item, "path") and hasattr(item, "methods"):
                rotas.append(item)
            elif hasattr(item, "original_router"):
                visitar(item.original_router.routes)
            elif hasattr(item, "routes"):
                visitar(item.routes)

    visitar(app.routes)
    return rotas


# Rotas que exigem corpo conhecido para serem chamadas com sentido; as demais
# recebem corpo vazio, e qualquer status de resposta e aceito -- o que importa
# e que o corpo da resposta, seja ele qual for, nao contenha a senha.
_FABRICAS_DE_CORPO = {
    ("POST", "/auth/register"): lambda senha: {
        "usuario": f"Sweep{uuid.uuid4().hex[:8]}",
        "senha": senha,
    },
    ("POST", "/auth/login"): lambda senha: {"usuario": "sweep-usuario-inexistente", "senha": senha},
}


def _valores_de(objeto):
    """Caminha um JSON decodificado e devolve so os valores-folha (nunca as chaves).

    Comparar contra os VALORES, e nao varrer o texto bruto atras da substring
    "senha", evita falso positivo com o nome do campo "senha" que aparece
    legitimamente em `loc` de erros de validacao e no schema do OpenAPI --
    isso seria testar o formato do erro, nao o vazamento do segredo (Artigo
    IX). O que a regra 4 da spec 002 probe e a SENHA (o valor) voltando numa
    resposta, nao o nome do campo.
    """
    if isinstance(objeto, dict):
        for valor in objeto.values():
            yield from _valores_de(valor)
    elif isinstance(objeto, list):
        for item in objeto:
            yield from _valores_de(item)
    elif isinstance(objeto, str):
        yield objeto


def test_nenhuma_rota_registrada_devolve_a_senha_ou_o_hash_no_corpo(sessao_db):
    """Dado qualquer endpoint da aplicacao, quando se inspeciona a
    resposta, entao a senha e o hash da senha nunca aparecem.

    Percorre as rotas de verdade registradas no app (nao uma lista
    hardcoded), para que o teste continue valendo quando a Fase 3 somar
    rotas nao previstas aqui.
    """
    senha_sentinela = "sentinela-do-sweep-98765"
    registro = client.post(
        "/auth/register",
        json={"usuario": f"Sentinela{uuid.uuid4().hex[:8]}", "senha": senha_sentinela},
    )
    token = registro.json()["token"]
    hash_guardado = professores_repo.buscar_por_usuario(
        sessao_db, registro.json()["professor"]["usuario"]
    ).senha_hash

    infratores = []
    for rota in _coletar_rotas_da_aplicacao():
        metodos = rota.methods - {"HEAD", "OPTIONS"}
        for metodo in metodos:
            if "{" in rota.path:
                continue  # exige um id que esta fase nao tem; coberto pelo teste de escopo
            fabrica = _FABRICAS_DE_CORPO.get((metodo, rota.path))
            corpo = fabrica(senha_sentinela) if fabrica else {}
            resposta = client.request(
                metodo,
                rota.path,
                json=corpo if metodo != "GET" else None,
                headers={"Authorization": f"Bearer {token}"},
            )
            try:
                corpo_resposta = resposta.json()
            except ValueError:
                continue
            valores = list(_valores_de(corpo_resposta))
            if senha_sentinela in valores or hash_guardado in valores:
                infratores.append(
                    f"{metodo} {rota.path} ({resposta.status_code}): {corpo_resposta}"
                )

    assert not infratores, "Vazamento de senha ou hash: " + "; ".join(infratores)


def test_senha_rejeitada_por_ser_curta_tambem_nao_pode_voltar_no_corpo_da_resposta(sessao_db):
    """A regra 4 da spec 002 e incondicional: "a senha ... nunca e devolvida
    por nenhum endpoint". O validador do Pydantic, por padrao, ecoa o valor
    rejeitado no campo `input` do erro 422 -- inclusive quando o campo
    rejeitado e a propria senha. Mesmo sendo a senha que o professor acabou
    de digitar (nao um segredo de outra conta), o criterio 11 pede para
    inspecionar QUALQUER resposta, e o texto da regra 4 nao abre excecao
    para respostas de erro.
    """
    senha_curta_mas_sensivel = "curta12"
    resposta = client.post(
        "/auth/register", json={"usuario": "SweepValidacao", "senha": senha_curta_mas_sensivel}
    )

    assert resposta.status_code == 422
    assert senha_curta_mas_sensivel not in resposta.text


# --- Regressao da revisao da Fase 2: envelope do 422 ------------------------
# CRITICO: nao havia handler de RequestValidationError, entao o 422 do
# Pydantic ecoava o valor rejeitado no campo `input` -- a senha voltava no
# corpo da resposta e dali para log de proxy, APM e devtools. Alem disso o
# 422 escapava do envelope {"erro": {...}} e chegava ao professor como texto
# de protocolo em ingles.


@pytest.mark.parametrize(
    ("caminho", "corpo", "senha"),
    [
        ("/auth/register", {"usuario": "professor_x", "senha": "curta12"}, "curta12"),
        ("/auth/register", {"usuario": "professor_y", "senha": "a" * 200}, "a" * 200),
        ("/auth/login", {"usuario": "professor_z", "senha": ""}, None),
    ],
)
def test_erro_de_validacao_nunca_devolve_a_senha_enviada(caminho, corpo, senha):
    resposta = client.post(caminho, json=corpo)
    assert resposta.status_code == 422
    texto = resposta.text
    if senha:
        assert senha not in texto
    assert '"input"' not in texto


def test_erro_de_validacao_sai_no_envelope_da_aplicacao():
    resposta = client.post("/auth/register", json={"usuario": "ab", "senha": "senhavalida1"})
    corpo = resposta.json()

    assert resposta.status_code == 422
    assert corpo["erro"]["codigo"] == "ENTRADA_INVALIDA"
    assert corpo["erro"]["mensagem"]
    assert "detail" not in corpo


def test_erro_de_validacao_diz_qual_campo_falhou_sem_o_valor():
    resposta = client.post("/auth/register", json={"usuario": "ok_assim", "senha": "curta"})
    campos = resposta.json()["erro"]["detalhes"]["campos"]

    assert any(campo["campo"] == "senha" for campo in campos)
    assert all("input" not in campo for campo in campos)
    # O contexto de um campo sensivel tambem nao volta: `ctx` carrega o limite,
    # mas em outros validadores pode carregar o valor.
    senha = next(campo for campo in campos if campo["campo"] == "senha")
    assert "contexto" not in senha


# --- Regressao da revisao da Fase 2: usuario so de espacos ------------------


@pytest.mark.parametrize("usuario", ["   ", "\t\t\t", "    \n  "])
def test_usuario_so_com_espacos_e_recusado(usuario, sessao_db):
    resposta = client.post("/auth/register", json={"usuario": usuario, "senha": "senhavalida123"})
    assert resposta.status_code == 422


def test_espacos_nas_pontas_do_usuario_sao_aparados(sessao_db):
    nome = "ComEspacosNasPontas"
    resposta = client.post(
        "/auth/register", json={"usuario": f"  {nome}  ", "senha": "senhavalida123"}
    )
    assert resposta.status_code == 201
    assert resposta.json()["professor"]["usuario"] == nome


# --- Regressao da revisao da Fase 2: limite_treinadores no perfil -----------
# MEDIO: o invariante 5 do SDD pede o limite derivado do nivel, e nao havia
# funcao, coluna nem campo de resposta que o calculasse.


def test_me_informa_quantos_treinadores_o_laboratorio_comporta(sessao_db):
    from app.game.laboratorio import limite_treinadores

    registro = client.post(
        "/auth/register", json={"usuario": "LimiteDeTreinadores", "senha": "senhavalida123"}
    )
    token = registro.json()["token"]

    perfil = client.get("/me", headers={"Authorization": f"Bearer {token}"}).json()

    assert perfil["laboratorio"]["limite_treinadores"] == limite_treinadores(1)
    assert perfil["laboratorio"]["limite_treinadores"] == balance.LIMITE_TREINADORES_NIVEL_1


def test_o_kit_inicial_nao_estoura_o_limite_do_laboratorio_novo(sessao_db):
    registro = client.post(
        "/auth/register", json={"usuario": "KitCabeNoLimite", "senha": "senhavalida123"}
    )
    token = registro.json()["token"]

    perfil = client.get("/me", headers={"Authorization": f"Bearer {token}"}).json()

    assert perfil["resumo"]["treinadores"] <= perfil["laboratorio"]["limite_treinadores"]


# --- Item 5 da constituicao: atomicidade ------------------------------------


def test_falha_no_meio_da_montagem_do_kit_nao_deixa_professor_nem_laboratorio_orfaos(
    sessao_db, monkeypatch
):
    """Artigo VII: o registro e tudo-ou-nada. Forca uma excecao depois que o
    professor e o laboratorio ja foram inseridos (mas nao commitados) na
    mesma transacao, e confirma que nenhuma linha sobra -- nem o professor.
    """

    def _quebrar(*_args, **_kwargs):
        raise RuntimeError("falha forcada para o teste de atomicidade (Artigo VII)")

    monkeypatch.setattr("app.services.auth.montar_kit_inicial", _quebrar)

    with pytest.raises(RuntimeError):
        client.post("/auth/register", json={"usuario": "Atomico", "senha": "senha-atomica1"})

    assert professores_repo.buscar_por_usuario(sessao_db, "Atomico") is None
