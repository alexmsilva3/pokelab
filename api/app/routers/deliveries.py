"""Rotas de `/deliveries` (spec 008): a Central de Entregas.

So traducao HTTP, como em todo `routers/` do PokeLab: quem decide prazo,
duracao, recompensa e atendibilidade e `services/entregas.py`, que por sua vez
so repassa o que `app.game.delivery` ja calculou (Artigo II).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencias import SessaoProfessor, professor_atual
from app.schemas.deliveries import EntregaAceitarEntrada, EntregaClaimLer, EntregaLer, ListaEntregas
from app.services import entregas as entregas_service

router = APIRouter(prefix="/deliveries", tags=["deliveries"])


@router.get("", response_model=ListaEntregas)
def listar_entregas(
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> ListaEntregas:
    """Estado observado, segundos para expirar e vagas para repor (criterios 18 e 22)."""
    return entregas_service.listar(sessao, sessao_professor.laboratorio.id)


@router.post("/refresh", response_model=ListaEntregas)
def regerar_entregas(
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> ListaEntregas:
    """Preenche vagas abertas (de graca) ou descarta a lista valida (com espera).

    Recusa 409 `AGUARDE_PARA_REGERAR` so quando nao ha vaga nenhuma a repor
    (criterio 22).
    """
    return entregas_service.refresh(sessao, sessao_professor.laboratorio.id)


@router.post("/{entrega_id}/accept", response_model=EntregaLer)
def aceitar_entrega(
    entrega_id: uuid.UUID,
    dados: EntregaAceitarEntrada,
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> EntregaLer:
    """O professor escolhe o treinador e os Pokemon (criterios 20, 23 a 26).

    Recusas 409: `ENTREGA_EXPIRADA`, `ENTREGA_NAO_DISPONIVEL`,
    `TREINADOR_OCUPADO`, `POKEMON_NAO_ATENDE_AO_PEDIDO`, `POKEMON_INDISPONIVEL`,
    `ULTIMO_POKEMON`. Entrega de outro laboratorio: 404, nunca 403 (criterio 32).
    """
    return entregas_service.aceitar(
        sessao,
        sessao_professor.laboratorio.id,
        entrega_id,
        dados.treinador_id,
        dados.pokemon_ids,
    )


@router.post("/{entrega_id}/claim", response_model=EntregaClaimLer)
def concluir_entrega(
    entrega_id: uuid.UUID,
    sessao_professor: SessaoProfessor = Depends(professor_atual),
    sessao: Session = Depends(get_db),
) -> EntregaClaimLer:
    """Resolve a entrega e credita a recompensa (ADR-006, criterios 27 a 30).

    Idempotente: a primeira chamada apos o prazo vencer resolve de fato; as
    seguintes releem o mesmo resultado ja gravado, sem mudar nada. Recusa 409
    `ENTREGA_EM_CURSO` antes do prazo.
    """
    return entregas_service.claim(sessao, sessao_professor.laboratorio.id, entrega_id)
