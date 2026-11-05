"""troca duracao base por custo de travessia e encontros base

A duracao da expedicao deixa de ser um numero por local e passa a ser calculada
pelo caminho: soma do custo de travessia dos locais percorridos mais o tempo de
exploracao do destino (SDD 4.3). Ritmo da sessao e rendimento da expedicao viram
decisoes separadas.

As colunas entram com default temporario porque a tabela ja esta populada; o
default e removido em seguida, e os valores reais chegam pelo seed.

Revision ID: a73b7240acbb
Revises: 1f20142eeefc
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a73b7240acbb"
down_revision: str | None = "1f20142eeefc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Valores de transicao, sobrescritos pelo seed logo depois.
CUSTO_PADRAO = 4
ENCONTROS_PADRAO = 3
DURACAO_PADRAO = 10


def upgrade() -> None:
    op.add_column(
        "locais",
        sa.Column(
            "custo_travessia_minutos",
            sa.Integer(),
            nullable=False,
            server_default=str(CUSTO_PADRAO),
        ),
    )
    op.add_column(
        "locais",
        sa.Column(
            "encontros_base",
            sa.Integer(),
            nullable=False,
            server_default=str(ENCONTROS_PADRAO),
        ),
    )
    op.alter_column("locais", "custo_travessia_minutos", server_default=None)
    op.alter_column("locais", "encontros_base", server_default=None)
    op.drop_column("locais", "duracao_base_minutos")


def downgrade() -> None:
    op.add_column(
        "locais",
        sa.Column(
            "duracao_base_minutos",
            sa.INTEGER(),
            autoincrement=False,
            nullable=False,
            server_default=str(DURACAO_PADRAO),
        ),
    )
    op.alter_column("locais", "duracao_base_minutos", server_default=None)
    op.drop_column("locais", "encontros_base")
    op.drop_column("locais", "custo_travessia_minutos")
