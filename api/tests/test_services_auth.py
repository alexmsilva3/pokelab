"""Registro atomico do kit inicial e login (spec 002, tarefa 6).

A spec 002 pede uma transacao so para o registro inteiro e um teste de
concorrencia para a concessao do kit (Artigo VII da constituicao).
"""

from __future__ import annotations

import threading
import uuid

import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.erros import CredenciaisInvalidas, UsuarioEmUso
from app.core.seguranca import verificar_senha
from app.game import balance
from app.models import (
    ItemEstoque,
    LocalDesbloqueado,
    PokedexEntrada,
    PokemonInstancia,
    Professor,
    Treinador,
)
from app.services import auth as auth_service
from tests.conftest import requer_banco

pytestmark = requer_banco


def test_registrar_cria_professor_laboratorio_e_kit_completo(sessao_db):
    resultado = auth_service.registrar(
        sessao_db,
        usuario="Ash",
        senha="pikachu123",
        nome_exibicao="Ash Ketchum",
        nome_laboratorio="Lab de Pallet",
    )

    assert resultado.professor.usuario == "Ash"
    assert resultado.laboratorio.nome == "Lab de Pallet"
    assert resultado.laboratorio.nivel == 1
    assert resultado.laboratorio.experiencia == 0
    assert resultado.laboratorio.moedas == 0
    assert resultado.laboratorio.starters_concedidos is True

    laboratorio_id = resultado.laboratorio.id

    pokemon = sessao_db.scalars(
        select(PokemonInstancia).where(PokemonInstancia.laboratorio_id == laboratorio_id)
    ).all()
    assert len(pokemon) == 3
    assert {p.especie_id for p in pokemon} == set(balance.STARTER_SPECIES_IDS)
    assert all(p.nivel == balance.STARTER_LEVEL for p in pokemon)
    assert all(p.treinador_id is None for p in pokemon)

    treinadores = sessao_db.scalars(
        select(Treinador).where(Treinador.laboratorio_id == laboratorio_id)
    ).all()
    assert len(treinadores) == balance.TREINADORES_NO_KIT_INICIAL

    itens = sessao_db.scalars(
        select(ItemEstoque).where(ItemEstoque.laboratorio_id == laboratorio_id)
    ).all()
    assert {i.item_id: i.quantidade for i in itens} == balance.ESTOQUE_INICIAL

    locais = sessao_db.scalars(
        select(LocalDesbloqueado).where(LocalDesbloqueado.laboratorio_id == laboratorio_id)
    ).all()
    assert [local.local_id for local in locais] == [balance.LOCAL_INICIAL_ID]

    pokedex = sessao_db.scalars(
        select(PokedexEntrada).where(PokedexEntrada.laboratorio_id == laboratorio_id)
    ).all()
    assert len(pokedex) == 3
    assert all(entrada.visto and entrada.capturado for entrada in pokedex)


def test_registrar_usuario_duplicado_em_qualquer_caixa_e_recusado(sessao_db):
    auth_service.registrar(sessao_db, usuario="Misty", senha="starmie9999")
    with pytest.raises(UsuarioEmUso):
        auth_service.registrar(sessao_db, usuario="MISTY", senha="outrasenha1")


def test_registrar_nao_guarda_a_senha_em_texto_legivel(sessao_db):
    resultado = auth_service.registrar(sessao_db, usuario="Brock", senha="onix123456")
    professor = sessao_db.get(Professor, resultado.professor.id)
    assert professor.senha_hash != "onix123456"
    assert verificar_senha("onix123456", professor.senha_hash)


def test_autenticar_senha_errada_e_usuario_inexistente_recusam_identico(sessao_db):
    auth_service.registrar(sessao_db, usuario="Gary", senha="eevee123456")

    with pytest.raises(CredenciaisInvalidas) as erro_senha_errada:
        auth_service.autenticar(sessao_db, usuario="Gary", senha="senha-errada")
    with pytest.raises(CredenciaisInvalidas) as erro_usuario_inexistente:
        auth_service.autenticar(sessao_db, usuario="ninguem-cadastrado", senha="qualquer-coisa")

    assert str(erro_senha_errada.value) == str(erro_usuario_inexistente.value)


def test_autenticar_com_credenciais_corretas_devolve_token(sessao_db):
    auth_service.registrar(sessao_db, usuario="Erika", senha="gloom123456")
    resultado = auth_service.autenticar(sessao_db, usuario="erika", senha="gloom123456")
    assert resultado.token
    assert resultado.professor.usuario == "Erika"


def test_registro_concorrente_com_mesmo_usuario_concede_o_kit_uma_unica_vez(sessao_db):
    """Artigo VII: duas tentativas de registro em paralelo, mesmo usuario.

    Cada thread abre a propria `Session`, porque o objeto nao e thread-safe; a
    disputa de verdade acontece no banco, na constraint unica de
    `usuario_normalizado`.
    """
    sucessos: list[uuid.UUID] = []
    falhas: list[UsuarioEmUso] = []
    trava = threading.Lock()

    def tentar() -> None:
        with SessionLocal() as sessao:
            try:
                resultado = auth_service.registrar(sessao, usuario="Serena", senha="fennekin123")
            except UsuarioEmUso as erro:
                with trava:
                    falhas.append(erro)
                return
            # O id e lido ainda dentro do `with`: a sessao fecha ao sair do
            # bloco, e o objeto ORM expira junto com ela.
            with trava:
                sucessos.append(resultado.laboratorio.id)

    threads = [threading.Thread(target=tentar) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(sucessos) == 1
    assert len(falhas) == 4

    professores = sessao_db.scalars(
        select(Professor).where(Professor.usuario_normalizado == "serena")
    ).all()
    assert len(professores) == 1

    pokemon = sessao_db.scalars(
        select(PokemonInstancia).where(PokemonInstancia.laboratorio_id == sucessos[0])
    ).all()
    assert len(pokemon) == 3
