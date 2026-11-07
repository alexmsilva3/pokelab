"""Fixtures compartilhadas pelos testes que precisam de Postgres.

Mesmo padrao de `test_seed_carga.py`: pula em vez de falhar quando o banco nao
esta acessivel, para que `pytest` continue util numa maquina sem
infraestrutura.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine
from app.seed import executar

# Ordem irrelevante: TRUNCATE ... CASCADE resolve as dependencias entre si.
# As tabelas de referencia (especies, locais, itens) ficam de fora: sao o
# acervo do seed, nao estado de teste.
TABELAS_DE_ESTADO = (
    "expedicao_eventos",
    "expedicao_itens",
    "expedicoes",
    "entrega_requisitos",
    "entregas",
    "pokemon_instancias",
    "treinadores",
    "pokedex_entradas",
    "pokedex_avistamentos",
    "locais_desbloqueados",
    "item_estoques",
    "laboratorios",
    "professores",
)


def _banco_disponivel() -> bool:
    try:
        with engine.connect():
            return True
    except OperationalError:
        return False


requer_banco = pytest.mark.skipif(
    not _banco_disponivel(),
    reason="Postgres indisponivel; rode com `make test-db` ou docker compose",
)


@pytest.fixture(scope="session", autouse=True)
def _acervo_carregado() -> None:
    """O kit inicial referencia especies, itens e o local de Pallet Town."""
    if not _banco_disponivel():
        return
    with SessionLocal() as sessao:
        executar(sessao)


@pytest.fixture
def sessao_db() -> Generator[Session, None, None]:
    """Sessao com as tabelas de estado limpas, isolando um teste do outro."""
    if not _banco_disponivel():
        pytest.skip("Postgres indisponivel; rode com `make test-db` ou docker compose")
    with SessionLocal() as sessao:
        sessao.execute(text(f"TRUNCATE {', '.join(TABELAS_DE_ESTADO)} RESTART IDENTITY CASCADE"))
        sessao.commit()
        yield sessao
        sessao.rollback()
