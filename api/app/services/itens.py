"""Caso de uso da mochila do laboratorio (spec 003)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.repositories import itens as itens_repo
from app.schemas.itens import ItemEmEstoqueLer, PaginaItens


def listar(sessao: Session, laboratorio_id: uuid.UUID) -> PaginaItens:
    linhas = itens_repo.listar_estoque(sessao, laboratorio_id)
    return PaginaItens(
        items=[
            ItemEmEstoqueLer(
                item_id=item.id,
                nome=item.nome,
                categoria=item.categoria,
                potencia=item.potencia,
                quantidade=quantidade,
            )
            for item, quantidade in linhas
        ]
    )
