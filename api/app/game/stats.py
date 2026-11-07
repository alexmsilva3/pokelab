"""Stats efetivos de um Pokemon individual (SDD 4.2).

O seed guarda o que a especie e; o que o individuo tem depende do nivel:

    hp_efetivo   = floor(hp_base * 2 * nivel / 100) + nivel + 10
    stat_efetivo = floor(stat_base * 2 * nivel / 100) + 5
    hp_atual     = max(1, round(hp_efetivo * hp_atual_pct / 100))

A Fase 7 acrescenta a recuperacao passiva do SDD 4.8, que anda no sentido
contrario do desgaste da expedicao:

    hp_recuperado = min(100, hp_atual_pct + minutos // MINUTOS_POR_PONTO_DE_HP)

E a formula das geracoes modernas sem IV, EV nem natureza: dois Pikachu de
nivel 20 sao identicos, por decisao (SDD 4.2). O HP tem bonus proprio para que
nivel baixo nao caia em um golpe.

Duas decisoes de implementacao valem o comentario.

A primeira: a conta e feita em aritmetica inteira e racional exata, nunca em
ponto flutuante. `round` de float carrega o erro de representacao, e a Fase 8
vai mexer nos multiplicadores de balance.py; um arredondamento que muda
conforme a calibragem transformaria o Artigo III em promessa. `Fraction` da o
mesmo empate para par que `round` define, sem o erro.

A segunda: `hp_atual_pct` zero devolve zero, e qualquer porcentagem positiva
devolve ao menos `HP_MINIMO_VIVO`. Sem esse piso, um Pokemon de 1% de um HP
baixo seria arredondado para zero e apareceria nocauteado sem ter caido; sem a
excecao do zero, nenhum Pokemon conseguiria estar nocauteado.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from app.game import balance
from app.game.erros import HpAtualInvalido, NivelInvalido, StatInvalido
from app.game.experience import NIVEL_MINIMO

# --- Entrada ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StatsBase:
    """Os seis stats-base de uma especie.

    Dataclass enxuta em vez do modelo ORM, como `EspecieInicial` do kit: o
    Artigo I nao sobreviveria a um `PokemonEspecie` do SQLAlchemy atravessando
    esta fronteira. Quem le o banco e `services/`, e mapeia os campos
    `*_base` da especie para os nomes daqui.
    """

    hp: int
    ataque: int
    defesa: int
    ataque_especial: int
    defesa_especial: int
    velocidade: int


# --- Saida -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StatsEfetivos:
    """Os seis stats ja calculados para o nivel do individuo."""

    hp: int
    ataque: int
    defesa: int
    ataque_especial: int
    defesa_especial: int
    velocidade: int


# --- Invariantes (Artigo VI) ------------------------------------------------


def _exigir_nivel_valido(nivel: int) -> None:
    """Invariante 7 do SDD 3.3: nenhum Pokemon passa do nivel 100."""
    if nivel < NIVEL_MINIMO or nivel > balance.NIVEL_MAXIMO:
        raise NivelInvalido(
            f"Nivel {nivel} fora da faixa valida de {NIVEL_MINIMO} a {balance.NIVEL_MAXIMO}."
        )


def _exigir_pct_valido(hp_atual_pct: int) -> None:
    if hp_atual_pct < 0 or hp_atual_pct > balance.BASE_PERCENTUAL:
        raise HpAtualInvalido(
            f"hp_atual_pct {hp_atual_pct} fora da faixa valida de 0 a {balance.BASE_PERCENTUAL}."
        )


def _exigir_stat_nao_negativo(nome: str, valor: int) -> None:
    if valor < 0:
        raise StatInvalido(f"O stat {nome} nao pode ser negativo: {valor}.")


def _exigir_base_valida(base: StatsBase) -> None:
    for nome, valor in (
        ("hp", base.hp),
        ("ataque", base.ataque),
        ("defesa", base.defesa),
        ("ataque_especial", base.ataque_especial),
        ("defesa_especial", base.defesa_especial),
        ("velocidade", base.velocidade),
    ):
        _exigir_stat_nao_negativo(nome, valor)


# --- Formulas ---------------------------------------------------------------


def _parcela_do_nivel(stat_base: int, nivel: int) -> int:
    """floor(stat_base * MULTIPLICADOR_STAT * nivel / DIVISOR_STAT_NIVEL).

    Divisao inteira de inteiros nao negativos: o piso ja sai do `//`.
    """
    return stat_base * balance.MULTIPLICADOR_STAT * nivel // balance.DIVISOR_STAT_NIVEL


def calcular_stats_efetivos(base: StatsBase, nivel: int) -> StatsEfetivos:
    """Os seis stats do individuo no nivel informado."""
    _exigir_nivel_valido(nivel)
    _exigir_base_valida(base)
    return StatsEfetivos(
        hp=_parcela_do_nivel(base.hp, nivel) + nivel + balance.BONUS_HP_FIXO,
        ataque=_parcela_do_nivel(base.ataque, nivel) + balance.BONUS_STAT_FIXO,
        defesa=_parcela_do_nivel(base.defesa, nivel) + balance.BONUS_STAT_FIXO,
        ataque_especial=_parcela_do_nivel(base.ataque_especial, nivel) + balance.BONUS_STAT_FIXO,
        defesa_especial=_parcela_do_nivel(base.defesa_especial, nivel) + balance.BONUS_STAT_FIXO,
        velocidade=_parcela_do_nivel(base.velocidade, nivel) + balance.BONUS_STAT_FIXO,
    )


def hp_atual_absoluto(hp_efetivo: int, hp_atual_pct: int) -> int:
    """Converte a porcentagem guardada no banco nos pontos de HP que a ficha mostra.

    A ficha diz "38 / 45", nao "84%". Nocauteado e nocauteado: pct zero devolve
    zero. Qualquer pct positivo devolve ao menos `HP_MINIMO_VIVO`, limitado ao
    proprio HP maximo para o caso degenerado de um hp_efetivo zerado.
    """
    _exigir_stat_nao_negativo("hp_efetivo", hp_efetivo)
    _exigir_pct_valido(hp_atual_pct)
    if hp_atual_pct == 0:
        return 0
    pontos = round(Fraction(hp_efetivo * hp_atual_pct, balance.BASE_PERCENTUAL))
    return min(hp_efetivo, max(balance.HP_MINIMO_VIVO, pontos))


# --- Recuperacao passiva (SDD 4.8) ------------------------------------------


def hp_recuperado(hp_atual_pct: int, minutos_decorridos: int) -> int:
    """`min(100, hp_atual_pct + minutos // MINUTOS_POR_PONTO_DE_HP)` (SDD 4.8).

    O Pokemon se cura sozinho enquanto esta no laboratorio, derivado do relogio
    como manda o ADR-004 — sem job, sem agendador, sem escrita. Em expedicao a
    enfermaria para: o invariante 18 e cumprido por quem chama, que materializa
    o HP no despacho e carimba `started_at`, e nao por esta funcao, que nao tem
    como saber onde o Pokemon esta.

    Tres decisoes valem o comentario.

    **Chegam MINUTOS, nao instantes.** Quem subtrai `agora` de
    `hp_atualizado_em` e o servico; o Artigo I proibe o dominio de ler o
    relogio, e receber o numero pronto e o que torna a funcao testavel sem
    congelar o tempo do processo. A conversao do relogio em minutos de jogo —
    inclusive `EXPEDITION_TIME_SCALE`, que e ambiente e nao calibragem — e da
    mesma camada.

    **Minuto negativo nao tira vida.** Um relogio de servidor que ande para
    tras, ou uma linha com `hp_atualizado_em` no futuro, produziriam uma
    recuperacao negativa e o Pokemon apareceria mais machucado do que voltou da
    expedicao. O piso em zero trata isso como "ainda nao passou tempo nenhum",
    que e a leitura honesta.

    **Nocauteado recupera igual.** A questao 8 do SDD decidiu que ninguem
    morre: um Pokemon em zero por cento esta exausto, nao perdido, e sobe um
    ponto no mesmo ritmo de qualquer outro. Sem isso, um time nocauteado ficaria
    permanentemente fora de jogo e o loop travaria na primeira derrota.
    """
    _exigir_pct_valido(hp_atual_pct)
    minutos = max(0, minutos_decorridos)
    ganho = minutos // balance.MINUTOS_POR_PONTO_DE_HP
    return min(balance.BASE_PERCENTUAL, hp_atual_pct + ganho)
