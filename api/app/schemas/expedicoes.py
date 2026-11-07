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
from typing import Any, Literal

from pydantic import BaseModel, field_serializer

from app.schemas.pokemon import PokemonResumo
from app.schemas.trainers import AvatarLer

# Os quatro valores que a coluna `status` grava (SDD 3.2) e os cinco que a
# leitura pode mostrar: `AGUARDANDO_RELATORIO` nao e gravado, e derivado a
# cada leitura por `game.expedition.estado_observado` (mesmo padrao de
# `EstadoDoLocalLer` em `schemas/mapa.py`).
StatusGravadoLer = Literal["EM_CURSO", "CONCLUIDA_SUCESSO", "CONCLUIDA_FALHA", "ABORTADA"]
EstadoObservadoLer = Literal[
    "EM_CURSO", "AGUARDANDO_RELATORIO", "CONCLUIDA_SUCESSO", "CONCLUIDA_FALHA", "ABORTADA"
]

# O status final que um relatorio de campo pode gravar (spec 007):
# `game.expedition.resolver` so devolve um dos dois — `ABORTADA` e decisao do
# professor, nunca resultado de campo, entao nunca aparece aqui.
StatusDoRelatorioLer = Literal["CONCLUIDA_SUCESSO", "CONCLUIDA_FALHA"]

# Uniao fechada compartilhada com o frontend (plan.md, contratos de API):
# `game.expedition.TipoDeEvento` e a fonte, repetida aqui porque schemas/ nao
# importa Enum de game/ para o contrato Pydantic (mesma distancia que o resto
# do modulo mantem do dominio).
TipoDeEventoLer = Literal[
    "PARTIDA",
    "BATALHA",
    "CAPTURA",
    "CAPTURA_FALHA",
    "BAGAGEM_CHEIA",
    "DESCOBERTA",
    "ITEM",
    "CONTRATEMPO",
    "SUBIU_NIVEL",
    "EVOLUCAO",
    "RETORNO",
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


# --- Relatorio de campo (spec 007) -------------------------------------------


class EventoDeExpedicaoLer(BaseModel):
    """Uma linha da linha do tempo: o que o professor le (plan.md, contratos de API)."""

    ordem: int
    tipo: TipoDeEventoLer
    texto: str
    ocorrido_em_minuto: int
    payload: dict[str, Any] | None = None


class CapturaDoRelatorioLer(BaseModel):
    """Um Pokemon capturado nesta expedicao, ja solto no laboratorio (regra 19)."""

    especie_id: int
    especie_nome: str
    nivel: int
    pokemon_id: uuid.UUID


class PokemonDoRelatorioLer(BaseModel):
    """O antes-e-depois de um Pokemon do time nesta expedicao."""

    pokemon_id: uuid.UUID
    especie_id: int
    especie_nome: str
    nivel_antes: int
    nivel_depois: int
    exp_ganha: int
    hp_antes_pct: int
    hp_depois_pct: int
    evoluiu_para_id: int | None = None
    evoluiu_para_nome: str | None = None


class GanhoDeExperienciaLer(BaseModel):
    """O ganho de experiencia de um nivel (treinador ou laboratorio) nesta expedicao."""

    nivel_antes: int
    nivel_depois: int
    exp_ganha: int


class ItemDoRelatorioLer(BaseModel):
    """Um item consumido em campo ou achado em campo, ja somado por identificador."""

    item_id: str
    nome: str
    quantidade: int


class EspecieVistaLer(BaseModel):
    """Uma especie enfrentada nesta expedicao, para o resumo da Pokedex."""

    especie_id: int
    nome: str
    primeira_vez: bool


class RelatorioDeCampoLer(BaseModel):
    """O relatorio inteiro: a linha do tempo mais o resumo (plan.md, contratos de API).

    So existe depois que `POST /expeditions/{id}/claim` resolve a expedicao;
    ate la, `ExpedicaoLer.relatorio` vem nulo.
    """

    status: StatusDoRelatorioLer
    resolvida_em: datetime
    encontros: int
    vitorias: int
    derrotas: int
    # Falso em falha, ou se o destino ja estava aberto antes desta expedicao
    # (regra 15 e 16 da spec 007).
    local_desbloqueado: bool
    eventos: list[EventoDeExpedicaoLer]
    capturas: list[CapturaDoRelatorioLer]
    time: list[PokemonDoRelatorioLer]
    treinador: GanhoDeExperienciaLer
    laboratorio: GanhoDeExperienciaLer
    itens_consumidos: list[ItemDoRelatorioLer]
    itens_encontrados: list[ItemDoRelatorioLer]
    especies_vistas: list[EspecieVistaLer]


class ExpedicaoResumoLer(BaseModel):
    """Uma linha de `GET /expeditions`, com o estado e o tempo restante
    calculados agora mesmo (revisao da Fase 7, achado 1).

    `status` e o que esta gravado (`EM_CURSO` | `CONCLUIDA_SUCESSO` |
    `CONCLUIDA_FALHA` | `ABORTADA`); `estado_observado` e esse mesmo valor
    corrigido pelo relogio (plan.md: "o estado que ninguem pediu") e pode
    valer `AGUARDANDO_RELATORIO` mesmo com `status` ainda `EM_CURSO`. A tela
    deve ler `estado_observado`, nunca `status` sozinho — e por isso os dois
    viajam juntos nesta resposta em vez de o cliente ter de rederivar um a
    partir do outro.

    Sem `relatorio`: a listagem e o painel que o professor abre toda hora, e
    com o historico crescendo sem teto, embutir a linha do tempo inteira de
    cada expedicao (eventos, texto, payload) nela multiplicava o peso da
    resposta por cada relatorio gravado. Quem quer o relatorio pede a ficha
    (`GET /expeditions/{id}`) ou reclama (`POST /expeditions/{id}/claim`); a
    listagem so diz QUE a expedicao tem relatorio, atraves de
    `estado_observado` e `status`, nunca o CONTEUDO dele.
    """

    id: uuid.UUID

    treinador_id: uuid.UUID
    treinador_nome: str
    # Retrato e time viajam junto com a expedicao para o cartao do painel poder
    # mostrar QUEM esta em campo e com o que — hoje so o nome aparecia, e o
    # professor tinha de abrir outra tela para lembrar o que mandou.
    #
    # O time e o do momento da leitura, e isso e correto e nao uma aproximacao:
    # o treinador esta ocupado, e o invariante 3 proibe alterar o time de quem
    # esta ocupado. O que esta no banco agora e o que partiu.
    treinador_avatar: AvatarLer
    treinador_time: list[PokemonResumo]

    local_destino_id: str
    local_destino_nome: str
    local_origem_id: str
    local_origem_nome: str

    status: StatusGravadoLer
    estado_observado: EstadoObservadoLer

    # Serializado como STRING (revisao da Fase 7, achado 2): o Artigo III
    # promete que a mesma semente reproduz o mesmo relatorio, mas semente real
    # passa facilmente de 2**53-1 — o maior inteiro que o IEEE 754 de 64 bits
    # do `JSON.parse` do navegador representa sem perda. Um `number` no corpo
    # perderia os digitos finais antes mesmo de chegar ao estado do React; uma
    # `string` atravessa JSON inteira, e o campo nunca e usado em aritmetica
    # no cliente (so exibicao/depuracao), entao a troca de tipo nao custa nada
    # a interface.
    seed: int

    @field_serializer("seed")
    def _serializar_seed(self, seed: int) -> str:
        return str(seed)

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


class ExpedicaoLer(ExpedicaoResumoLer):
    """A ficha completa de uma expedicao: `ExpedicaoResumoLer` mais o relatorio.

    Resposta de `GET /expeditions/{id}` e do `expedicao` dentro de
    `POST /expeditions/{id}/claim` — os dois lugares em que o professor pede
    uma expedicao especifica, nunca a listagem.
    """

    # Nulo ate a expedicao resolver (spec 007): o relatorio so nasce no
    # `POST /expeditions/{id}/claim`, e este `GET` continua sem escrever nada.
    relatorio: RelatorioDeCampoLer | None = None


class ListaExpedicoes(BaseModel):
    """`GET /expeditions`: sem paginacao por pagina/tamanho (plan.md).

    Limitada por `limite` no SERVIDOR (revisao da Fase 7, achado 1), nao por
    pagina: o painel sempre pede as N expedicoes mais recentes de um
    laboratorio — nunca "a pagina 7" — entao um parametro com teto resolve o
    uso real sem o custo de um cursor que ninguem navega. `total` continua
    sendo a contagem de `items` nesta pagina (equivalente a `len(items)`), nao
    o total historico do laboratorio: expor o total historico exigiria uma
    segunda consulta so para um numero que a tela nao usa.
    """

    items: list[ExpedicaoResumoLer]
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


class ExpedicaoClaimLer(BaseModel):
    """Resposta de `POST /expeditions/{id}/claim` (plan.md, contratos de API).

    `expedicao` e a mesma `ExpedicaoLer` de sempre, com `status` ja terminal;
    `relatorio` repete o que `expedicao.relatorio` traz, como campo proprio no
    topo da resposta — e o momento do jogo que o ADR-006 criou, e merece um
    lugar de destaque no corpo, nao so um campo aninhado.
    """

    expedicao: ExpedicaoLer
    relatorio: RelatorioDeCampoLer
