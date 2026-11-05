"""Progressao do laboratorio: nivel, experiencia e capacidade (SDD 4.1).

Dominio puro. O laboratorio e o unico eixo de progressao do professor: nao ha
limite fixo de expedicoes simultaneas, entao quantos treinadores cabem aqui e
quantas expedicoes podem correr ao mesmo tempo sao a mesma pergunta.
"""

from __future__ import annotations

from app.game import balance
from app.game.erros import ErroDeDominio


class NivelDeLaboratorioInvalido(ErroDeDominio):
    """O nivel do laboratorio e menor que 1."""


def _exigir_nivel_valido(nivel: int) -> None:
    if nivel < 1:
        raise NivelDeLaboratorioInvalido(f"Nivel de laboratorio invalido: {nivel}.")


def limite_treinadores(nivel_laboratorio: int) -> int:
    """Quantos treinadores o laboratorio comporta neste nivel (invariante 5)."""
    _exigir_nivel_valido(nivel_laboratorio)
    return balance.LIMITE_TREINADORES_NIVEL_1 + (nivel_laboratorio - 1) * (
        balance.TREINADORES_POR_NIVEL_LABORATORIO
    )


def experiencia_total_para_nivel(nivel: int) -> int:
    """Experiencia acumulada para o laboratorio estar neste nivel."""
    _exigir_nivel_valido(nivel)
    return balance.EXP_LAB_BASE * (nivel - 1) ** 2


def nivel_para_experiencia(experiencia: int) -> int:
    """O inverso. Nivel 1 comeca em zero de experiencia."""
    if experiencia < 0:
        raise NivelDeLaboratorioInvalido(f"Experiencia de laboratorio negativa: {experiencia}.")
    nivel = 1
    while experiencia >= experiencia_total_para_nivel(nivel + 1):
        nivel += 1
    return nivel
