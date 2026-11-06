"""Contrato de `/trainers` (spec 004, secao 5.3 do SDD).

Entrada e saida sao classes separadas (Artigo II). `TimeEntrada` e o unico
schema de entrada desta rota, compartilhado por `PUT .../team` (grava) e
`POST .../team/preview` (so valida): os dois recebem exatamente a mesma forma,
e a Fase 4 nao reimplementa a validacao numa segunda classe so para o nome
ficar diferente.

Poder, capacidade de bagagem e experiencia para o proximo nivel nunca entram
aqui: sao derivados pelo servidor e so aparecem do lado da saida (Artigo II).
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.schemas.pokemon import PokemonResumo

# --- Entrada -----------------------------------------------------------------


class TimeEntrada(BaseModel):
    """A composicao pretendida. Sem limite de tamanho aqui de proposito:

    uma lista de quatro nao e erro de formato, e sim de regra de jogo
    (TIME_CHEIO, 409) — recusar com 422 antes de chegar ao dominio esconderia
    o motivo que a previa e o salvamento existem para mostrar.
    """

    pokemon_ids: list[uuid.UUID]


# --- Saida ---------------------------------------------------------------


class AvatarLer(BaseModel):
    iniciais: str
    cor: str


class TrainerResumo(BaseModel):
    """O que a lista mostra: nome, avatar, nivel, status, time e bagagem (secao 4)."""

    id: uuid.UUID
    nome: str
    avatar: AvatarLer
    nivel: int
    experiencia: int
    status: str
    # Derivados pelo dominio e enviados prontos (Artigo II). Sem eles o cliente
    # reimplementava o invariante 3 e o tamanho maximo de time por conta
    # propria, e passaria a divergir em silencio na primeira recalibragem.
    ocupado: bool
    tamanho_maximo_time: int
    time: list[PokemonResumo]
    capacidade_bagagem: int


class TrainerDetalhe(TrainerResumo):
    """A ficha: os mesmos campos da lista, mais o que so faz sentido ao abrir um."""

    # Nulo no nivel maximo, como PokemonDetalhe ja fazia: zero mentiria
    # dizendo que nao falta nada.
    experiencia_para_proximo_nivel: int | None
    poder: float


class ListaTrainers(BaseModel):
    """Sem paginacao de proposito: o laboratorio tem exatamente tres (plan.md)."""

    items: list[TrainerResumo]


class PreviaTimeLer(BaseModel):
    """Resultado de `POST .../team/preview`: valida sem gravar (secao 6 do plano).

    `poder` e `capacidade_bagagem` descrevem a composicao pretendida quando ela
    e valida, e o time ATUAL do treinador quando nao e — uma composicao
    recusada nao muda nada, entao nao ha poder "da composicao impossivel" para
    mostrar.
    """

    valido: bool
    poder: float
    capacidade_bagagem: int
    codigo: str | None = None
    motivo: str | None = None
