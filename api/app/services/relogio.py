"""Conversao de tempo de relogio em minutos de jogo (ADR-004, SDD 4.8).

`game.stats.hp_recuperado` so aceita MINUTOS DE JOGO; ler `datetime.now()` e
`EXPEDITION_TIME_SCALE` e trabalho do servico, nao do dominio — o Artigo I
proibe os dois dentro de `app.game`. Este modulo e a fronteira: ele sabe a
hora e sabe a escala, o dominio so sabe a formula.

Mora aqui, e nao em `schemas/`, porque e calculo de aplicacao (le o relogio e
a configuracao), nao forma de contrato: um schema de saida recebe o `pct` ja
derivado como argumento simples, nunca o `pokemon` cru para derivar sozinho.
"""

from __future__ import annotations

from datetime import datetime

from app.game.stats import hp_recuperado


def minutos_de_jogo(desde: datetime, agora: datetime, escala: float) -> int:
    """Quantos minutos de JOGO se passaram entre `desde` e `agora`.

    `escala` multiplica a duracao das expedicoes (ADR-004): com 0,01, uma
    expedicao de 20 minutos de jogo dura 12 segundos de relogio — o relogio
    real anda `1/escala` vezes mais rapido em minutos de jogo, e e por isso
    que a conversao divide por `escala` em vez de multiplicar.

    Minuto negativo (relogio andando para tras, ou `desde` no futuro por um
    instante de corrida) vira zero aqui mesmo: `hp_recuperado` tambem poe um
    piso, mas tratar o caso aqui evita depender de outro modulo para um
    resultado que so esta fronteira pode produzir.
    """
    if escala <= 0:
        return 0
    decorridos_reais = (agora - desde).total_seconds() / 60
    if decorridos_reais <= 0:
        return 0
    return int(decorridos_reais / escala)


def hp_observado(
    hp_atual_pct: int, hp_atualizado_em: datetime, *, agora: datetime, escala: float
) -> int:
    """O `hp_atual_pct` que toda leitura deve mostrar: o gravado mais a recuperacao passiva.

    Serve para qualquer Pokemon, em campo ou no laboratorio — o invariante 18
    ja garante que `hp_atualizado_em` de quem esta em expedicao nao avanca (o
    despacho materializa e carimba `started_at`), entao esta mesma conta
    devolve o valor congelado sem precisar saber onde o Pokemon esta.
    """
    minutos = minutos_de_jogo(hp_atualizado_em, agora, escala)
    return hp_recuperado(hp_atual_pct, minutos)
