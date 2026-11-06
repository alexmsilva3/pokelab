"""Contrato de `GET /map` e `GET /map/{id}` (spec 005, plan.md).

Entrada e saida continuam em classes separadas (Artigo II): o unico campo de
entrada desta fase e `treinador_id`, em querystring, e ele chega como
parametro de rota, nao num corpo — por isso nao ha classe de entrada aqui.

`origem_id`/`origem_nome`, `caminho`, `custo_viagem_minutos` e
`duracao_estimada_minutos` sao `None` quando o local esta fora de alcance;
`proximo_passo_id`/`proximo_passo_nome` sao `None` quando ele ja e alcancavel
ou esta visitado. A API nunca troca esse `None` por zero ou string vazia
(secao 5 do plano): um 0 min mentiria dizendo que a viagem nao custa nada.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

EstadoDoLocalLer = Literal["VISITADO", "ALCANCAVEL", "FORA_DE_ALCANCE"]


class LocalNoMapaLer(BaseModel):
    """Uma linha de `GET /map`: o que o professor ve sem abrir o local."""

    id: str
    nome: str
    tipo: str
    nivel_dificuldade: int
    nivel_selvagem_min: int
    nivel_selvagem_max: int

    estado: EstadoDoLocalLer

    origem_id: str | None
    origem_nome: str | None
    duracao_estimada_minutos: int | None

    proximo_passo_id: str | None
    proximo_passo_nome: str | None


class MapaLer(BaseModel):
    """Os dez locais sempre, qualquer que seja o progresso (regra 1)."""

    items: list[LocalNoMapaLer]
    visitados: int
    total: int


class EspecieAvistadaLer(BaseModel):
    """Uma especie que os treinadores deste laboratorio ja viram neste local.

    So existe para quem ja foi visto (regra 9): nao ha estado "desconhecida"
    aqui, como existe em `schemas/pokedex.py` — a lista inteira esta ausente
    em vez de conter uma versao vazia da entrada (regras 8 e 10, criterio 12).
    """

    especie_id: int
    nome: str
    sprite: str
    vezes_visto: int
    primeiro_visto_em: datetime


class LocalDetalhadoLer(LocalNoMapaLer):
    """`GET /map/{id}`: a linha do mapa mais o que so faz sentido ao abrir.

    `encontros_base` pode ir ao cliente — e quantos encontros a expedicao
    gera, nao quais (secao do plano "o que a resposta nao pode conter").
    `especies_avistadas` nunca contem contagem do total de especies do local:
    isso revelaria quantas existem para quem nunca foi (mesma secao).
    """

    encontros_base: int
    especies_avistadas: list[EspecieAvistadaLer]
