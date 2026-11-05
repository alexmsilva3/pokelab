"""Acesso a tabela `professores`.

Regra 2 da spec 002: o usuario e unico sem diferenciar maiusculas. A busca e a
criacao normalizam para minusculas antes de tocar o banco; a constraint unica
em `usuario_normalizado` e quem torna isso impossivel de violar sob
concorrencia.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Professor


def normalizar(usuario: str) -> str:
    return usuario.strip().lower()


def buscar_por_usuario(sessao: Session, usuario: str) -> Professor | None:
    """Busca por usuario, sem diferenciar maiusculas de minusculas."""
    return sessao.scalar(
        select(Professor).where(Professor.usuario_normalizado == normalizar(usuario))
    )


def buscar_por_id(sessao: Session, professor_id: uuid.UUID) -> Professor | None:
    return sessao.get(Professor, professor_id)


def criar(sessao: Session, *, usuario: str, senha_hash: str, nome_exibicao: str) -> Professor:
    professor = Professor(
        usuario=usuario.strip(),
        usuario_normalizado=normalizar(usuario),
        senha_hash=senha_hash,
        nome_exibicao=nome_exibicao,
    )
    sessao.add(professor)
    sessao.flush()
    return professor


def marcar_acesso(sessao: Session, professor: Professor, agora: datetime) -> None:
    professor.ultimo_acesso = agora
