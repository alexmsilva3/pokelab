"""Contrato de `/deliveries` (spec 008, plan.md).

Entrada e saida sao classes separadas (Artigo II). `EntregaAceitarEntrada` e o
unico schema de entrada: o professor manda QUAIS Pokemon e QUAL treinador, e o
servidor deriva prazo, duracao e recompensa sempre — nenhum dos tres chega
pela entrada.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.expedicoes import GanhoDeExperienciaLer

# O que a coluna `status` grava, mais `EXPIRADA`, derivada a cada leitura por
# `game.delivery.estado_observado_entrega` (mesmo padrao de
# `EstadoObservadoLer` em `schemas/expedicoes.py`).
EstadoObservadoEntregaLer = Literal["DISPONIVEL", "EXPIRADA", "EM_CURSO", "CONCLUIDA", "DESCARTADA"]

# --- Entrada -----------------------------------------------------------------


class EntregaAceitarEntrada(BaseModel):
    """O que o professor escolhe ao aceitar (plan.md, contratos de API).

    Duracao, `eta` e recompensa nunca entram aqui: o servidor e quem deriva os
    tres, sempre (Artigo II).
    """

    treinador_id: uuid.UUID
    pokemon_ids: list[uuid.UUID]


# --- Saida -------------------------------------------------------------------


class RequisitoLer(BaseModel):
    """Uma linha do pedido, com quantos exemplares o viveiro ja tem hoje."""

    especie_id: int
    especie_nome: str
    quantidade: int
    disponiveis_no_viveiro: int


class EntregaLer(BaseModel):
    """Uma linha de `GET /deliveries` (plan.md, contratos de API)."""

    id: uuid.UUID
    titulo: str
    local_destino_id: str
    local_destino_nome: str

    estado_observado: EstadoObservadoEntregaLer
    # Nulo quando o estado nao e DISPONIVEL: o prazo e da OFERTA, nao da
    # missao (SDD 4.9), e so faz sentido contar enquanto ela e oferta.
    segundos_para_expirar: int | None

    requisitos: list[RequisitoLer]

    # Se o professor pode aceitar HOJE, com o viveiro como esta agora, e por
    # que nao — derivado pelo servico (Artigo II), nunca pelo cliente.
    atendivel: bool
    motivo: str | None

    # Preview enquanto DISPONIVEL (estimado com os Pokemon do viveiro que
    # atendem hoje); valor REAL, gravado no aceite, a partir de EM_CURSO.
    duracao_minutos: int | None
    recompensa_moedas: int | None
    recompensa_exp_laboratorio: int | None
    recompensa_exp_treinador: int | None

    # So existem a partir do aceite.
    treinador_id: uuid.UUID | None
    eta: datetime | None
    segundos_restantes: int | None


class ListaEntregas(BaseModel):
    """`GET /deliveries` e `POST /deliveries/refresh` devolvem o mesmo corpo."""

    items: list[EntregaLer]
    vagas_para_repor: int
    # Zero quando a lista valida ja pode ser descartada agora (invariante 15).
    segundos_para_regerar: int


# --- Conclusao (tarefa 14, ADR-006) ------------------------------------------


class PokemonEntregueLer(BaseModel):
    """Um Pokemon que saiu do laboratorio nesta entrega (SDD 4.9)."""

    especie_nome: str
    nivel: int


class ResultadoDeEntregaLer(BaseModel):
    """O que `POST /deliveries/{id}/claim` credita (plan.md, contratos de API)."""

    pokemon_entregues: list[PokemonEntregueLer]
    moedas_ganhas: int
    moedas_total: int
    laboratorio: GanhoDeExperienciaLer
    treinador: GanhoDeExperienciaLer
    lugares_liberados: int


class EntregaClaimLer(BaseModel):
    """Resposta de `POST /deliveries/{id}/claim`."""

    entrega: EntregaLer
    resultado: ResultadoDeEntregaLer
