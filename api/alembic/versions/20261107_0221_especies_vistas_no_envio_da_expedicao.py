"""especies vistas no envio da expedicao

Revision ID: 11a593488232
Revises: 56e14a9bb239
Create Date: 2026-11-07 02:21:43.579341+00:00

Achado 3 da revisao adversarial da Fase 7: `_montar_contexto` lia
`pokedex_repo.buscar_vistas` no instante do `claim`, fora de qualquer lock —
violando a letra do invariante 19 ("o resultado de uma expedicao e funcao
apenas da semente e do estado gravado no envio") e, pior, permitindo que
`claim`s concorrentes do mesmo laboratorio lessem a mesma Pokedex "antes de
qualquer um gravar" e todos anunciassem `DESCOBERTA` da mesma especie.

`expedicoes.especies_vistas_no_envio` grava o retrato da Pokedex no DESPACHO:
a lista de `especie_id` que o laboratorio ja tinha visto naquele instante. O
`claim` passa a ler so esta coluna, nunca mais a Pokedex ao vivo.

Nao ha como saber retroativamente o que uma expedicao ja em `EM_CURSO` viu no
proprio envio — o default no servidor existe so para essas linhas antigas
(lista vazia: na pior hipotese, uma delas repete uma `DESCOBERTA` que a
Pokedex atual ja tem, o que e inocuo e nunca o contrario). Removido logo
depois, para que um `INSERT` futuro que esqueca a coluna quebre alto, nao em
silencio — mesmo padrao de `pokemon_instancias.hp_atualizado_em`
(20261106_2300).

downgrade derruba a coluna.
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '11a593488232'
down_revision: str | None = '56e14a9bb239'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'expedicoes',
        sa.Column(
            'especies_vistas_no_envio',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column('expedicoes', 'especies_vistas_no_envio', server_default=None)


def downgrade() -> None:
    op.drop_column('expedicoes', 'especies_vistas_no_envio')
