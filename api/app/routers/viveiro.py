"""Rota de `GET /ranch` (spec 008): o viveiro do laboratorio."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencias import SessaoProfessor, professor_atual
from app.schemas.viveiro import EstadoDoViveiroLer
from app.services import viveiro as viveiro_service

router = APIRouter(prefix="/ranch", tags=["ranch"])


@router.get("", response_model=EstadoDoViveiroLer)
def obter_viveiro(
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> EstadoDoViveiroLer:
    """Ocupacao, capacidade e transbordo do viveiro (criterios 1 e 2)."""
    return viveiro_service.obter(sessao, sessao_professor.laboratorio.id)
