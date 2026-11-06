"""Contrato de `GET /items` (spec 003)."""

from __future__ import annotations

from pydantic import BaseModel


class ItemEmEstoqueLer(BaseModel):
    item_id: str
    nome: str
    categoria: str
    potencia: float
    quantidade: int


class PaginaItens(BaseModel):
    items: list[ItemEmEstoqueLer]
