"""Rota `GET /me`: perfil do professor autenticado (spec 002)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencias import SessaoProfessor, professor_atual
from app.repositories import resumo as resumo_repo
from app.schemas.auth import LaboratorioLer, PerfilLer, ProfessorLer, ResumoLer

router = APIRouter(tags=["perfil"])


@router.get("/me", response_model=PerfilLer)
def meu_perfil(
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> PerfilLer:
    resumo = resumo_repo.contar(sessao, sessao_professor.laboratorio.id)
    return PerfilLer(
        professor=ProfessorLer.model_validate(sessao_professor.professor),
        laboratorio=LaboratorioLer.de_modelo(sessao_professor.laboratorio),
        resumo=ResumoLer.model_validate(resumo),
    )
