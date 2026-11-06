"""Rota `GET /pokedex` (spec 003)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencias import SessaoProfessor, professor_atual
from app.schemas.pokedex import PokedexLer
from app.services import pokedex as pokedex_service

router = APIRouter(tags=["pokedex"])


@router.get("/pokedex", response_model=PokedexLer)
def obter_pokedex(
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> PokedexLer:
    return pokedex_service.listar(sessao, sessao_professor.laboratorio.id)
