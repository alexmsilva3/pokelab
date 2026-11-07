"""Acesso ao estoque de itens de um laboratorio (spec 003).

`ItemEstoque` e so laboratorio/item/quantidade; nome, categoria e potencia
vem da tabela de referencia `itens` e sao juntados aqui para a mochila nao
precisar de uma segunda ida ao banco por item.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models import Item, ItemEstoque


def listar_estoque(sessao: Session, laboratorio_id: uuid.UUID) -> list[tuple[Item, int]]:
    """Item mais quantidade, so o que tem estoque (regra 11: zero nao aparece)."""
    return list(
        sessao.execute(
            select(Item, ItemEstoque.quantidade)
            .join(ItemEstoque, ItemEstoque.item_id == Item.id)
            .where(ItemEstoque.laboratorio_id == laboratorio_id, ItemEstoque.quantidade > 0)
            .order_by(Item.categoria, Item.nome)
        ).all()
    )


def buscar_itens_referencia(sessao: Session, item_ids: Sequence[str]) -> dict[str, Item]:
    """Os itens do catalogo de seed pedidos numa carga (Artigo V: so leitura).

    Sem lock de proposito: `itens` e tabela de referencia, imutavel em
    runtime, e travar uma linha que ninguem escreve so prenderia a transacao
    por nada. Um `item_id` ausente do retorno nao existe no seed — quem chama
    decide o que fazer com isso.
    """
    if not item_ids:
        return {}
    itens = sessao.scalars(select(Item).where(Item.id.in_(item_ids)))
    return {item.id: item for item in itens}


def _quantidades(linhas: Sequence[tuple[str, int]]) -> dict[str, int]:
    return dict(linhas)


def buscar_quantidades(
    sessao: Session, laboratorio_id: uuid.UUID, item_ids: Sequence[str]
) -> dict[str, int]:
    """O estoque de cada item pedido, sem lock — para a previa, que nao grava.

    Um `item_id` ausente do dicionario nao tem linha de estoque para este
    laboratorio, o que vale zero: nunca houve e nunca saiu nada dele.
    """
    if not item_ids:
        return {}
    linhas = sessao.execute(
        select(ItemEstoque.item_id, ItemEstoque.quantidade).where(
            ItemEstoque.laboratorio_id == laboratorio_id, ItemEstoque.item_id.in_(item_ids)
        )
    ).all()
    return _quantidades(linhas)


def travar_quantidades(
    sessao: Session, laboratorio_id: uuid.UUID, item_ids: Sequence[str]
) -> dict[str, int]:
    """`SELECT ... FOR UPDATE` no estoque da carga, em ordem deterministica por id.

    A ordem por `item_id` e o que evita deadlock contra outro despacho
    concorrente que peça os mesmos itens: as duas transacoes travam as
    mesmas linhas sempre na mesma sequencia (plan.md da spec 006, mesmo
    raciocinio de `treinadores_repo.travar_pokemon_envolvidos`).

    Sem `populate_existing` (auditoria da revisao da Fase 7, mesma pergunta
    feita a `laboratorios_repo.travar`): o despacho nunca chama
    `buscar_quantidades` antes deste lock na mesma transacao — so a previa faz
    isso, numa requisicao separada — entao nenhum `ItemEstoque` chega
    pre-carregado no identity map. Primeira leitura, sem objeto obsoleto para
    este `with_for_update()` deixar de atualizar.
    """
    if not item_ids:
        return {}
    linhas = sessao.execute(
        select(ItemEstoque.item_id, ItemEstoque.quantidade)
        .where(ItemEstoque.laboratorio_id == laboratorio_id, ItemEstoque.item_id.in_(item_ids))
        .order_by(ItemEstoque.item_id)
        .with_for_update()
    ).all()
    return _quantidades(linhas)


def debitar_condicional(
    sessao: Session, laboratorio_id: uuid.UUID, item_id: str, quantidade: int
) -> bool:
    """Debita do estoque so se houver o suficiente; devolve se debitou.

    `UPDATE ... WHERE quantidade >= :n` em vez de ler-depois-escrever: zero
    linhas afetadas significa estoque insuficiente, nunca quantidade
    negativa e nunca um sucesso silencioso (invariante 9, plan.md secao 5).
    Com as linhas ja travadas por `travar_quantidades` na mesma transacao,
    este UPDATE so pode falhar por um bug de calculo anterior — e e
    exatamente por isso que ele existe como segunda linha de defesa, nao
    como a unica.
    """
    resultado = sessao.execute(
        update(ItemEstoque)
        .where(
            ItemEstoque.laboratorio_id == laboratorio_id,
            ItemEstoque.item_id == item_id,
            ItemEstoque.quantidade >= quantidade,
        )
        .values(quantidade=ItemEstoque.quantidade - quantidade)
    )
    return resultado.rowcount == 1


def creditar(sessao: Session, laboratorio_id: uuid.UUID, item_id: str, quantidade: int) -> None:
    """Soma `quantidade` ao estoque (regra 18 da spec 007: achados de campo).

    `INSERT ... ON CONFLICT DO UPDATE` em vez de ler-depois-escrever: cria a
    linha na primeira vez que o laboratorio acha este item, e soma quando ela
    ja existe — atomico mesmo com duas resolucoes concorrentes do mesmo
    laboratorio creditando o mesmo item, sem precisar de um `SELECT ... FOR
    UPDATE` separado antes.
    """
    instrucao = pg_insert(ItemEstoque).values(
        laboratorio_id=laboratorio_id, item_id=item_id, quantidade=quantidade
    )
    sessao.execute(
        instrucao.on_conflict_do_update(
            index_elements=[ItemEstoque.laboratorio_id, ItemEstoque.item_id],
            set_={"quantidade": ItemEstoque.quantidade + instrucao.excluded.quantidade},
        )
    )
