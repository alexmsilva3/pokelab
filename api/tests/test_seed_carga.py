"""Carga do acervo no Postgres.

Exige um banco acessivel. Fora do container (ou sem db de pe) os testes sao
pulados, para que `pytest` continue util numa maquina sem infraestrutura.

O seed faz upsert, entao rodar isto contra o banco de desenvolvimento nao
destroi estado de partida.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.models import Item, Local, LocalEncontro, PokemonEspecie
from app.seed import executar

TOTAL_ESPECIES = 151
TOTAL_LOCAIS = 10
TOTAL_ITENS = 6


def _banco_disponivel() -> bool:
    try:
        with engine.connect():
            return True
    except OperationalError:
        return False


pytestmark = pytest.mark.skipif(
    not _banco_disponivel(), reason="Postgres indisponivel; rode com `make test` ou docker compose"
)


@pytest.fixture(scope="module")
def sessao() -> Session:
    with SessionLocal() as sessao:
        executar(sessao)
        yield sessao


def _contar(sessao: Session, modelo) -> int:
    return sessao.scalar(select(func.count()).select_from(modelo))


def test_carrega_as_151_especies(sessao):
    assert _contar(sessao, PokemonEspecie) == TOTAL_ESPECIES


def test_carrega_os_dez_locais(sessao):
    assert _contar(sessao, Local) == TOTAL_LOCAIS


def test_carrega_os_itens(sessao):
    assert _contar(sessao, Item) == TOTAL_ITENS


def test_todo_local_tem_encontro_no_banco(sessao):
    sem_pool = sessao.scalars(
        select(Local.id).where(~Local.id.in_(select(LocalEncontro.local_id).distinct()))
    ).all()
    assert not sem_pool


def test_carga_repetida_nao_duplica_nem_falha(sessao):
    antes = (
        _contar(sessao, PokemonEspecie),
        _contar(sessao, Local),
        _contar(sessao, LocalEncontro),
        _contar(sessao, Item),
    )
    executar(sessao)
    depois = (
        _contar(sessao, PokemonEspecie),
        _contar(sessao, Local),
        _contar(sessao, LocalEncontro),
        _contar(sessao, Item),
    )
    assert antes == depois


def test_relacionamento_de_evolucao_resolve_no_banco(sessao):
    charmander = sessao.get(PokemonEspecie, 4)
    assert charmander.evolui_para_id == 5
    charmeleon = sessao.get(PokemonEspecie, charmander.evolui_para_id)
    assert charmeleon.nome == "Charmeleon"


def test_soma_de_stats_base_e_calculada(sessao):
    mew = sessao.get(PokemonEspecie, 151)
    assert mew.soma_stats_base == 600


def test_pallet_town_e_o_unico_local_inicial(sessao):
    iniciais = sessao.scalars(select(Local.id).where(Local.e_inicial.is_(True))).all()
    assert list(iniciais) == ["pallet-town"]
