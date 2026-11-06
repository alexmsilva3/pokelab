"""Acesso ao estoque de itens de um laboratorio (spec 003).

`ItemEstoque` e so laboratorio/item/quantidade; nome, categoria e potencia
vem da tabela de referencia `itens` e sao juntados aqui para a mochila nao
precisar de uma segunda ida ao banco por item.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
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
