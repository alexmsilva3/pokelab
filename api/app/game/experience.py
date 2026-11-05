"""Curvas de crescimento dos Pokemon (SDD 4.1).

Experiencia acumulada para estar no nivel n, por curva:

    rapida        = 0.8  * n^3
    media_rapida  =        n^3
    media_lenta   = 1.2  * n^3 - 15 * n^2 + 100 * n - 140
    lenta         = 1.25 * n^3

Duas decisoes de implementacao valem o comentario.

A primeira: o nivel 1 custa zero em todas as curvas. Sem essa normalizacao,
`media_rapida` cobraria 1 de experiencia de um Pokemon recem-nascido e
`media_lenta` cobraria -53, que nao e um numero de experiencia. O polinomio da
`media_lenta` so fica positivo a partir do nivel 2, e o piso em zero trata isso
em vez de deixar o negativo vazar para o resto do jogo.

A segunda: as tabelas sao calculadas uma vez, na importacao, com aritmetica
racional exata (`Fraction`). Ponto flutuante acertaria todos os valores com as
constantes de hoje, mas a Fase 8 vai mexer nesses multiplicadores, e um
arredondamento que muda conforme a calibragem transformaria o Artigo III em
promessa. Com a tabela pronta, o nivel e o inverso da experiencia viram uma
busca binaria, e os dois sentidos sao consistentes por construcao.
"""

from __future__ import annotations

from bisect import bisect_right
from enum import StrEnum
from fractions import Fraction
from math import floor
from typing import Final

from app.game import balance
from app.game.erros import CurvaDesconhecida, ExperienciaInvalida, NivelInvalido


class CurvaCrescimento(StrEnum):
    """As quatro curvas usadas pelo seed, nos mesmos nomes de `data/seed/`."""

    RAPIDA = "rapida"
    MEDIA_RAPIDA = "media_rapida"
    MEDIA_LENTA = "media_lenta"
    LENTA = "lenta"


def curva_de(valor: str | CurvaCrescimento) -> CurvaCrescimento:
    """Converte o texto do seed em curva, recusando o que nao reconhece."""
    try:
        return CurvaCrescimento(valor)
    except ValueError:
        nomes = ", ".join(curva.value for curva in CurvaCrescimento)
        raise CurvaDesconhecida(
            f"Curva de crescimento desconhecida: {valor!r}. Esperado uma de: {nomes}."
        ) from None


def _racional(constante: float) -> Fraction:
    """Converte a constante de balance.py em racional exato.

    `Fraction(str(0.8))` da 4/5; `Fraction(0.8)` daria a aproximacao binaria.
    """
    return Fraction(str(constante))


def _experiencia_bruta(curva: CurvaCrescimento, nivel: int) -> Fraction:
    cubo = nivel**3
    match curva:
        case CurvaCrescimento.RAPIDA:
            return _racional(balance.CURVA_RAPIDA) * cubo
        case CurvaCrescimento.MEDIA_RAPIDA:
            return _racional(balance.CURVA_MEDIA_RAPIDA) * cubo
        case CurvaCrescimento.LENTA:
            return _racional(balance.CURVA_LENTA) * cubo
        case CurvaCrescimento.MEDIA_LENTA:
            return (
                _racional(balance.CURVA_MEDIA_LENTA_A) * cubo
                - _racional(balance.CURVA_MEDIA_LENTA_B) * nivel**2
                + _racional(balance.CURVA_MEDIA_LENTA_C) * nivel
                - _racional(balance.CURVA_MEDIA_LENTA_D)
            )


NIVEL_MINIMO: Final[int] = 1


def _montar_tabela(curva: CurvaCrescimento) -> tuple[int, ...]:
    """Experiencia acumulada do nivel 1 ate NIVEL_MAXIMO, em ordem."""
    totais: list[int] = [0]
    for nivel in range(NIVEL_MINIMO + 1, balance.NIVEL_MAXIMO + 1):
        totais.append(max(0, floor(_experiencia_bruta(curva, nivel))))
    return tuple(totais)


_TABELAS: Final[dict[CurvaCrescimento, tuple[int, ...]]] = {
    curva: _montar_tabela(curva) for curva in CurvaCrescimento
}


def tabela_da_curva(curva: str | CurvaCrescimento) -> tuple[int, ...]:
    """Tabela completa da curva, indice 0 = nivel 1. Util para graficos e tuning."""
    return _TABELAS[curva_de(curva)]


def experiencia_total_para_nivel(curva: str | CurvaCrescimento, nivel: int) -> int:
    """Experiencia acumulada que um Pokemon precisa ter para ESTAR no nivel."""
    if nivel < NIVEL_MINIMO or nivel > balance.NIVEL_MAXIMO:
        raise NivelInvalido(
            f"Nivel {nivel} fora da faixa valida de {NIVEL_MINIMO} a {balance.NIVEL_MAXIMO}."
        )
    return tabela_da_curva(curva)[nivel - 1]


def nivel_para_experiencia(curva: str | CurvaCrescimento, experiencia: int) -> int:
    """Nivel correspondente a uma experiencia acumulada, saturando em NIVEL_MAXIMO.

    Invariante 7 do SDD 3.3: nenhum Pokemon passa do nivel 100, por mais
    experiencia que acumule.
    """
    if experiencia < 0:
        raise ExperienciaInvalida(f"Experiencia acumulada nao pode ser negativa: {experiencia}.")
    tabela = tabela_da_curva(curva)
    return bisect_right(tabela, experiencia)


def experiencia_para_o_proximo_nivel(curva: str | CurvaCrescimento, experiencia: int) -> int:
    """Quanto falta para subir. Zero quando ja esta no nivel maximo."""
    nivel = nivel_para_experiencia(curva, experiencia)
    if nivel >= balance.NIVEL_MAXIMO:
        return 0
    return experiencia_total_para_nivel(curva, nivel + 1) - experiencia
