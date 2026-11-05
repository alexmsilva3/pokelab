"""Acesso a tabela `laboratorios`.

A constraint unique em `professor_id` e como a regra 5 da spec 002 ("cada
conta tem exatamente um laboratorio") vira regra de banco.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Laboratorio

NIVEL_INICIAL = 1
EXPERIENCIA_INICIAL = 0
MOEDAS_INICIAIS = 0


def criar(sessao: Session, *, professor_id: uuid.UUID, nome: str) -> Laboratorio:
    """Cria o laboratorio nivel 1, zero experiencia e zero moedas (regra 6)."""
    laboratorio = Laboratorio(
        professor_id=professor_id,
        nome=nome,
        nivel=NIVEL_INICIAL,
        experiencia=EXPERIENCIA_INICIAL,
        moedas=MOEDAS_INICIAIS,
        starters_concedidos=False,
    )
    sessao.add(laboratorio)
    sessao.flush()
    return laboratorio


def buscar_por_professor_id(sessao: Session, professor_id: uuid.UUID) -> Laboratorio | None:
    return sessao.scalar(select(Laboratorio).where(Laboratorio.professor_id == professor_id))


def buscar_por_id(sessao: Session, laboratorio_id: uuid.UUID) -> Laboratorio | None:
    return sessao.get(Laboratorio, laboratorio_id)


def travar_para_concessao(sessao: Session, laboratorio_id: uuid.UUID) -> Laboratorio | None:
    """Trava a linha do laboratorio ate o fim da transacao (Artigo VII).

    Sem o lock, duas concessoes concorrentes sobre o MESMO laboratorio leem
    `starters_concedidos = False` as duas e as duas seguem em frente. A unique
    de `professor_id` protege o caminho do registro, mas nao protege uma
    segunda chamada a concessao sobre um laboratorio que ja existe.
    """
    return sessao.scalar(
        select(Laboratorio).where(Laboratorio.id == laboratorio_id).with_for_update()
    )


def marcar_starters_concedidos(sessao: Session, laboratorio: Laboratorio) -> None:
    """Invariante 10 do SDD 3.3: os starters sao concedidos exatamente uma vez."""
    laboratorio.starters_concedidos = True
