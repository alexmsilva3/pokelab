"""Rota `GET /items` (spec 003)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencias import SessaoProfessor, professor_atual
from app.schemas.itens import PaginaItens
from app.services import itens as itens_service

router = APIRouter(tags=["itens"])


@router.get("/items", response_model=PaginaItens)
def obter_mochila(
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> PaginaItens:
    return itens_service.listar(sessao, sessao_professor.laboratorio.id)
