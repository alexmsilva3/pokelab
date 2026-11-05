"""Migracao inicial vazia: ancora da cadeia de revisoes.

Revision ID: 0001_inicial
Revises:
Create Date: 2026-11-05
"""
from collections.abc import Sequence

revision: str = "0001_inicial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
