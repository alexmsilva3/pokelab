"""Rotas de credenciais: `POST /auth/register` e `POST /auth/login` (spec 002)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import LaboratorioLer, LoginEntrada, ProfessorLer, RegistroEntrada, SessaoLer
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["autenticacao"])


def _sessao_ler(resultado: auth_service.SessaoCriada) -> SessaoLer:
    return SessaoLer(
        token=resultado.token,
        professor=ProfessorLer.model_validate(resultado.professor),
        laboratorio=LaboratorioLer.de_modelo(resultado.laboratorio),
    )


@router.post("/register", response_model=SessaoLer, status_code=201)
def registrar(dados: RegistroEntrada, sessao: Session = Depends(get_db)) -> SessaoLer:
    resultado = auth_service.registrar(
        sessao,
        usuario=dados.usuario,
        senha=dados.senha,
        nome_exibicao=dados.nome_exibicao,
        nome_laboratorio=dados.nome_laboratorio,
    )
    return _sessao_ler(resultado)


@router.post("/login", response_model=SessaoLer)
def login(dados: LoginEntrada, sessao: Session = Depends(get_db)) -> SessaoLer:
    resultado = auth_service.autenticar(sessao, usuario=dados.usuario, senha=dados.senha)
    return _sessao_ler(resultado)
