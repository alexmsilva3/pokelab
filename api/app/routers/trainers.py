"""Rotas do corpo de treinadores do laboratorio (spec 004): leitura e time.

Sem `POST /trainers` nem `DELETE /trainers/{id}`: a v1 nao recruta nem
dispensa (regra 12 da spec 004, questoes 3 e 4 do SDD resolvidas). O corpo de
treinadores e exatamente o que o kit inicial concedeu.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencias import SessaoProfessor, professor_atual
from app.schemas.trainers import ListaTrainers, PreviaTimeLer, TimeEntrada, TrainerDetalhe
from app.services import trainers as trainers_service

router = APIRouter(prefix="/trainers", tags=["trainers"])


@router.get("", response_model=ListaTrainers)
def listar_treinadores(
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> ListaTrainers:
    return trainers_service.listar(sessao, sessao_professor.laboratorio.id)


@router.get("/{treinador_id}", response_model=TrainerDetalhe)
def obter_treinador(
    treinador_id: uuid.UUID,
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> TrainerDetalhe:
    return trainers_service.obter_detalhe(sessao, sessao_professor.laboratorio.id, treinador_id)


@router.put("/{treinador_id}/team", response_model=TrainerDetalhe)
def definir_time(
    treinador_id: uuid.UUID,
    dados: TimeEntrada,
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> TrainerDetalhe:
    """Substituicao total: quem nao esta em `pokemon_ids` volta ao laboratorio."""
    return trainers_service.definir_time(
        sessao, sessao_professor.laboratorio.id, treinador_id, dados.pokemon_ids
    )


@router.post("/{treinador_id}/team/preview", response_model=PreviaTimeLer)
def prever_time(
    treinador_id: uuid.UUID,
    dados: TimeEntrada,
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> PreviaTimeLer:
    """So valida: nenhuma linha do banco muda com esta chamada.

    E `POST` e nao `GET` porque a entrada e uma lista de UUIDs, que em query
    string fica feia e esbarra em limite de tamanho (plan.md) — a semantica
    continua sendo a de leitura.
    """
    return trainers_service.prever_time(
        sessao, sessao_professor.laboratorio.id, treinador_id, dados.pokemon_ids
    )
