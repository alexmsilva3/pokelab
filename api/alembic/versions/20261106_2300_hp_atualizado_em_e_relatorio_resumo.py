"""hp_atualizado_em e relatorio_resumo

Revision ID: 56e14a9bb239
Revises: 3bf20e8d3865
Create Date: 2026-11-06 23:00:00.000000+00:00

Fase 7 (spec 007): duas colunas para fechar o loop do jogo.

`pokemon_instancias.hp_atualizado_em` marca desde quando a recuperacao
passiva do SDD 4.8 conta (ADR-004): o despacho materializa o HP recuperado e
carimba `started_at`, a resolucao grava o HP desgastado e carimba
`resolvida_em`, e toda leitura deriva a partir daqui. As linhas existentes
nao tem como saber esse instante retroativamente, entao o default no
servidor e `now()` no momento da migracao — equivalente a dizer "a
recuperacao destas comeca a contar agora", que e a leitura honesta para um
Pokemon que ja estava parado no laboratorio.

`expedicoes.relatorio_resumo` guarda o resumo do relatorio de campo (tudo que
nao e a linha do tempo, que mora em `expedicao_eventos`): capturas com o
`pokemon_id` gerado, antes-e-depois de cada Pokemon do time, ganho de
experiencia de treinador e de laboratorio com nivel antes/depois, itens
consumidos e achados, e se o destino foi desbloqueado. Sem esta coluna, uma
segunda leitura da MESMA expedicao resolvida precisaria recalcular esses
numeros a partir do estado atual de treinador e laboratorio — que muda a
cada expedicao nova que eles completam depois desta — e o relatorio de uma
missao antiga mentiria sobre quanto ela rendeu na hora. Nula enquanto a
expedicao nao resolve.

downgrade derruba as duas colunas.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '56e14a9bb239'
down_revision: str | None = '3bf20e8d3865'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'pokemon_instancias',
        sa.Column(
            'hp_atualizado_em',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('now()'),
        ),
    )
    # O default no servidor so existe para as linhas ja existentes; novas
    # linhas gravam o instante explicito (despacho, resolucao ou criacao do
    # kit inicial), igual a `capturado_em`. Removido apos o backfill para que
    # um `INSERT` futuro que esqueca a coluna quebre alto, nao em silencio.
    op.alter_column('pokemon_instancias', 'hp_atualizado_em', server_default=None)

    op.add_column(
        'expedicoes',
        sa.Column('relatorio_resumo', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('expedicoes', 'relatorio_resumo')
    op.drop_column('pokemon_instancias', 'hp_atualizado_em')
