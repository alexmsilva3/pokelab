"""Contrato de `/expeditions` (spec 006, plan.md).

Entrada e saida sao classes separadas (Artigo II). `ExpedicaoEntrada` e o
unico schema de entrada, compartilhado por `POST /expeditions` (grava) e
`POST /expeditions/preview` (so valida) — mesmo padrao de `TimeEntrada` na
Fase 4: previa e despacho recebem exatamente a mesma forma.

Duracao, `eta`, dificuldade e chance nunca entram pela entrada: quem calcula
e o servidor, sempre (Artigo II). `quantidade` de um item nao tem limite
inferior aqui de proposito — uma carga com zero ou item repetido nao e erro
de formato, e sim recusa de dominio (`CARGA_INVALIDA`, 409) —, e recusar com
422 antes de chegar ao dominio esconderia o motivo que a previa existe para
mostrar.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Os quatro valores que a coluna `status` grava (SDD 3.2) e os cinco que a
# leitura pode mostrar: `AGUARDANDO_RELATORIO` nao e gravado, e derivado a
# cada leitura por `game.expedition.estado_observado` (mesmo padrao de
# `EstadoDoLocalLer` em `schemas/mapa.py`).
StatusGravadoLer = Literal["EM_CURSO", "CONCLUIDA_SUCESSO", "CONCLUIDA_FALHA", "ABORTADA"]
EstadoObservadoLer = Literal[
    "EM_CURSO", "AGUARDANDO_RELATORIO", "CONCLUIDA_SUCESSO", "CONCLUIDA_FALHA", "ABORTADA"
]

# --- Entrada -----------------------------------------------------------------


class ItemDaCargaEntrada(BaseModel):
    """Uma linha da mochila que o treinador leva."""

    item_id: str
    quantidade: int


class ExpedicaoEntrada(BaseModel):
    """O que o professor escolhe para despachar ou prever (plan.md secao 5)."""

    treinador_id: uuid.UUID
    local_id: str
    carga: list[ItemDaCargaEntrada] = []


# --- Saida ---------------------------------------------------------------


class ItemDaCargaLer(BaseModel):
    """Uma linha da carga, como a ficha da expedicao mostra."""

    item_id: str
    nome: str
    quantidade_levada: int
    quantidade_consumida: int


class ExpedicaoLer(BaseModel):
    """Uma expedicao, com o estado e o tempo restante calculados agora mesmo.

    `status` e o que esta gravado (`EM_CURSO` | `CONCLUIDA_SUCESSO` |
    `CONCLUIDA_FALHA` | `ABORTADA`); `estado_observado` e esse mesmo valor
    corrigido pelo relogio (plan.md: "o estado que ninguem pediu") e pode
    valer `AGUARDANDO_RELATORIO` mesmo com `status` ainda `EM_CURSO`. A tela
    deve ler `estado_observado`, nunca `status` sozinho — e por isso os dois
    viajam juntos nesta resposta em vez de o cliente ter de rederivar um a
    partir do outro.
    """

    id: uuid.UUID

    treinador_id: uuid.UUID
    treinador_nome: str

    local_destino_id: str
    local_destino_nome: str
    local_origem_id: str
    local_origem_nome: str

    status: StatusGravadoLer
    estado_observado: EstadoObservadoLer

    seed: int
    started_at: datetime
    eta: datetime
    resolvida_em: datetime | None

    duracao_minutos: int
    dificuldade_calculada: float
    poder_time_calculado: float

    # Derivado a cada leitura por `game.expedition.tempo_restante` (Artigo
    # II): o cliente nunca subtrai `eta - agora` por conta propria.
    # Nulo em estado terminal: o `eta` de uma expedicao abortada e o prazo de
    # uma viagem que nao vai mais acontecer.
    segundos_restantes: int | None

    carga: list[ItemDaCargaLer]


class ListaExpedicoes(BaseModel):
    """Sem paginacao por pagina/tamanho (plan.md): so `items` e `total`."""

    items: list[ExpedicaoLer]
    total: int


class PreviaDespachoLer(BaseModel):
    """Resultado de `POST /expeditions/preview`: a mesma validacao, sem gravar.

    Quando `valido` e falso, os demais campos vem nulos — uma expedicao
    recusada nao tem duracao nem `eta`, e inventar os dois so para preencher a
    tela prometeria um prazo que nao existe (mesmo raciocinio de
    `PreviaTimeLer` e de `game.expedition.PreviaDoDespacho`).
    """

    valido: bool

    duracao_minutos: int | None = None
    eta_estimado: datetime | None = None
    dificuldade: float | None = None
    chance_estimada: float | None = None
    capacidade_bagagem: int | None = None

    codigo: str | None = None
    motivo: str | None = None
