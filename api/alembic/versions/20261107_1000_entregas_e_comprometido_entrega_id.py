"""entregas, entrega_requisitos e comprometido_entrega_id

Revision ID: d6f81108a2bc
Revises: 11a593488232
Create Date: 2026-11-07 10:00:00.000000+00:00

Fase 8 (spec 008): a Central de Entregas precisa de duas tabelas novas —
`entregas` e `entrega_requisitos` — e de uma coluna nova em
`pokemon_instancias` para marcar quem esta reservado para uma delas
(invariante 14 do SDD 3.3). `laboratorios.entregas_geradas_em` e
`laboratorios.moedas` ja existem desde a Fase 3 (migracao
20261105_2036_tabelas_de_estado_do_laboratorio): nada muda la.

A coluna nova entra nula e sem `server_default`: todo Pokemon existente antes
desta migracao nasceu livre, e nulo e exatamente "livre" (game.viveiro).

downgrade derruba a coluna e as duas tabelas, nesta ordem (a FK obriga).
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd6f81108a2bc'
down_revision: str | None = '11a593488232'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'entregas',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('laboratorio_id', sa.UUID(), nullable=False),
        sa.Column('titulo', sa.String(length=160), nullable=False),
        sa.Column('local_destino_id', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('treinador_id', sa.UUID(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('eta', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolvida_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duracao_minutos', sa.Integer(), nullable=True),
        sa.Column('recompensa_moedas', sa.Integer(), nullable=True),
        sa.Column('recompensa_exp_laboratorio', sa.Integer(), nullable=True),
        sa.Column('recompensa_exp_treinador', sa.Integer(), nullable=True),
        sa.Column('gerada_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expira_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'resultado_resumo', postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.ForeignKeyConstraint(['laboratorio_id'], ['laboratorios.id']),
        sa.ForeignKeyConstraint(['local_destino_id'], ['locais.id']),
        sa.ForeignKeyConstraint(['treinador_id'], ['treinadores.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_entregas_laboratorio_status', 'entregas', ['laboratorio_id', 'status'], unique=False
    )

    op.create_table(
        'entrega_requisitos',
        sa.Column('entrega_id', sa.UUID(), nullable=False),
        sa.Column('especie_id', sa.Integer(), nullable=False),
        sa.Column('quantidade', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['entrega_id'], ['entregas.id']),
        sa.ForeignKeyConstraint(['especie_id'], ['pokemon_especies.id']),
        sa.PrimaryKeyConstraint('entrega_id', 'especie_id'),
    )

    op.add_column(
        'pokemon_instancias',
        sa.Column('comprometido_entrega_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        'fk_pokemon_instancias_comprometido_entrega_id_entregas',
        'pokemon_instancias',
        'entregas',
        ['comprometido_entrega_id'],
        ['id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_pokemon_instancias_comprometido_entrega_id_entregas',
        'pokemon_instancias',
        type_='foreignkey',
    )
    op.drop_column('pokemon_instancias', 'comprometido_entrega_id')
    op.drop_table('entrega_requisitos')
    op.drop_index('ix_entregas_laboratorio_status', table_name='entregas')
    op.drop_table('entregas')
