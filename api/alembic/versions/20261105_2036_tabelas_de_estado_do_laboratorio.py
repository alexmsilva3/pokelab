"""tabelas de estado do laboratorio

Seis tabelas novas para a spec 002: professores, laboratorios, treinadores,
pokemon_instancias, item_estoques, locais_desbloqueados e pokedex_entradas.
Todas nascem vazias, entao nenhuma coluna precisa de default de transicao.

`pokemon_instancias.comprometido_entrega_id` do SDD 3.2 fica de fora: a tabela
`entregas` ainda nao existe, e entra na Fase 8.

Revision ID: a41f3d9617c2
Revises: a73b7240acbb
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a41f3d9617c2"
down_revision: str | None = "a73b7240acbb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "professores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("usuario", sa.String(length=50), nullable=False),
        sa.Column("usuario_normalizado", sa.String(length=50), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("nome_exibicao", sa.String(length=80), nullable=False),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ultimo_acesso", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario_normalizado"),
    )
    op.create_table(
        "laboratorios",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("professor_id", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=80), nullable=False),
        sa.Column("nivel", sa.Integer(), nullable=False),
        sa.Column("experiencia", sa.Integer(), nullable=False),
        sa.Column("moedas", sa.Integer(), nullable=False),
        sa.Column("starters_concedidos", sa.Boolean(), nullable=False),
        sa.Column("entregas_geradas_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["professor_id"], ["professores.id"]),
        sa.PrimaryKeyConstraint("id"),
        # E assim que "um laboratorio por conta" (regra 5 da spec 002) vira
        # regra de banco, resistente a registro concorrente.
        sa.UniqueConstraint("professor_id"),
    )
    op.create_table(
        "item_estoques",
        sa.Column("laboratorio_id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.String(length=50), nullable=False),
        sa.Column("quantidade", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["itens.id"]),
        sa.ForeignKeyConstraint(["laboratorio_id"], ["laboratorios.id"]),
        sa.PrimaryKeyConstraint("laboratorio_id", "item_id"),
    )
    op.create_table(
        "locais_desbloqueados",
        sa.Column("laboratorio_id", sa.UUID(), nullable=False),
        sa.Column("local_id", sa.String(length=50), nullable=False),
        sa.Column(
            "desbloqueado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["laboratorio_id"], ["laboratorios.id"]),
        sa.ForeignKeyConstraint(["local_id"], ["locais.id"]),
        sa.PrimaryKeyConstraint("laboratorio_id", "local_id"),
    )
    op.create_table(
        "pokedex_entradas",
        sa.Column("laboratorio_id", sa.UUID(), nullable=False),
        sa.Column("especie_id", sa.Integer(), nullable=False),
        sa.Column("visto", sa.Boolean(), nullable=False),
        sa.Column("capturado", sa.Boolean(), nullable=False),
        sa.Column("primeiro_visto_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["especie_id"], ["pokemon_especies.id"]),
        sa.ForeignKeyConstraint(["laboratorio_id"], ["laboratorios.id"]),
        sa.PrimaryKeyConstraint("laboratorio_id", "especie_id"),
    )
    op.create_table(
        "treinadores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("laboratorio_id", sa.UUID(), nullable=False),
        sa.Column("nome", sa.String(length=50), nullable=False),
        sa.Column("avatar", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("nivel", sa.Integer(), nullable=False),
        sa.Column("experiencia", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expedicoes_concluidas", sa.Integer(), nullable=False),
        sa.Column("entregas_concluidas", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["laboratorio_id"], ["laboratorios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_treinadores_laboratorio_id"), "treinadores", ["laboratorio_id"], unique=False
    )
    op.create_table(
        "pokemon_instancias",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("laboratorio_id", sa.UUID(), nullable=False),
        sa.Column("especie_id", sa.Integer(), nullable=False),
        sa.Column("apelido", sa.String(length=50), nullable=True),
        sa.Column("nivel", sa.Integer(), nullable=False),
        sa.Column("experiencia", sa.Integer(), nullable=False),
        sa.Column("hp_atual_pct", sa.Integer(), nullable=False),
        sa.Column("treinador_id", sa.UUID(), nullable=True),
        sa.Column("origem", sa.String(length=20), nullable=False),
        sa.Column("local_captura_id", sa.String(length=50), nullable=True),
        sa.Column("capturado_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["especie_id"], ["pokemon_especies.id"]),
        sa.ForeignKeyConstraint(["laboratorio_id"], ["laboratorios.id"]),
        sa.ForeignKeyConstraint(["local_captura_id"], ["locais.id"]),
        sa.ForeignKeyConstraint(["treinador_id"], ["treinadores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_pokemon_instancias_laboratorio_id"),
        "pokemon_instancias",
        ["laboratorio_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_pokemon_instancias_laboratorio_id"), table_name="pokemon_instancias")
    op.drop_table("pokemon_instancias")
    op.drop_index(op.f("ix_treinadores_laboratorio_id"), table_name="treinadores")
    op.drop_table("treinadores")
    op.drop_table("pokedex_entradas")
    op.drop_table("locais_desbloqueados")
    op.drop_table("item_estoques")
    op.drop_table("laboratorios")
    op.drop_table("professores")
