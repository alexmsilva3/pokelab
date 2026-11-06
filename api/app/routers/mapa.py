"""Rotas `GET /map` e `GET /map/{id}` (spec 005).

So leitura: nenhuma destas rotas desbloqueia local, resolve expedicao nem
grava avistamento. Nomes de rota em ingles e singular, como o resto da API,
mas aqui `/map` e nao `/maps` — o contrato exato vem do plan.md da spec 005,
que trata o mapa como um recurso unico por laboratorio, nunca uma colecao.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencias import SessaoProfessor, professor_atual
from app.schemas.mapa import LocalDetalhadoLer, MapaLer
from app.services import mapa as mapa_service

router = APIRouter(prefix="/map", tags=["map"])


@router.get("", response_model=MapaLer)
def obter_mapa(
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> MapaLer:
    return mapa_service.obter_mapa(sessao, sessao_professor.laboratorio.id)


@router.get("/{local_id}", response_model=LocalDetalhadoLer)
def obter_local(
    local_id: str,
    treinador_id: uuid.UUID | None = None,
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> LocalDetalhadoLer:
    return mapa_service.obter_local(sessao, sessao_professor.laboratorio.id, local_id, treinador_id)
