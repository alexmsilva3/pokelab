"""Rotas de `/expeditions` (spec 006).

So traducao HTTP, como em todo `routers/` do PokeLab: quem calcula duracao,
dificuldade, chance e tempo restante e `services/expedicoes.py`, que por sua
vez so repassa o que `app.game.expedition` ja decidiu (Artigo II).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencias import SessaoProfessor, professor_atual
from app.schemas.expedicoes import (
    EstadoObservadoLer,
    ExpedicaoEntrada,
    ExpedicaoLer,
    ListaExpedicoes,
    PreviaDespachoLer,
)
from app.services import expedicoes as expedicoes_service

router = APIRouter(prefix="/expeditions", tags=["expeditions"])


@router.get("", response_model=ListaExpedicoes)
def listar_expedicoes(
    status: Annotated[list[EstadoObservadoLer] | None, Query()] = None,
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> ListaExpedicoes:
    """Ativas e historico (regra 14: so as do proprio laboratorio)."""
    return expedicoes_service.listar(sessao, sessao_professor.laboratorio.id, status)


@router.post("", response_model=ExpedicaoLer, status_code=201)
def despachar_expedicao(
    dados: ExpedicaoEntrada,
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> ExpedicaoLer:
    return expedicoes_service.despachar(
        sessao, sessao_professor.laboratorio.id, dados.treinador_id, dados.local_id, dados.carga
    )


@router.post("/preview", response_model=PreviaDespachoLer)
def prever_expedicao(
    dados: ExpedicaoEntrada,
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> PreviaDespachoLer:
    """So valida: nenhuma linha do banco muda com esta chamada (plan.md secao 8)."""
    return expedicoes_service.prever(
        sessao, sessao_professor.laboratorio.id, dados.treinador_id, dados.local_id, dados.carga
    )


@router.get("/{expedicao_id}", response_model=ExpedicaoLer)
def obter_expedicao(
    expedicao_id: uuid.UUID,
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> ExpedicaoLer:
    """Expedicao de outro laboratorio: 404, nunca 403 (criterio 13)."""
    return expedicoes_service.obter(sessao, sessao_professor.laboratorio.id, expedicao_id)


@router.delete("/{expedicao_id}", response_model=ExpedicaoLer)
def abortar_expedicao(
    expedicao_id: uuid.UUID,
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> ExpedicaoLer:
    """Aborta: treinador livre na hora, itens nao voltam (criterio 12)."""
    return expedicoes_service.abortar(sessao, sessao_professor.laboratorio.id, expedicao_id)
