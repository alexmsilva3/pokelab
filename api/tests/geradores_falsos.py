"""Geradores de teste que satisfazem `GeradorAleatorio` (Artigo III).

Dois tipos, com propositos diferentes.

`GeradorRoteirizado` devolve exatamente os valores que o teste escreveu, na
ordem em que os escreveu. E com ele que se verifica a borda de um sorteio por
peso e a ordem das rolagens, sem depender de nenhuma implementacao de PRNG.

`GeradorSemeado` e um `random.Random` de verdade, importado AQUI e nao no
dominio: o teste pode usar `random`, o modulo de `app/game/` nao. E ele que
prova o determinismo por semente — duas execucoes com a mesma semente dao o
mesmo resultado.
"""

from __future__ import annotations

from collections.abc import Sequence
from random import Random
from typing import TypeVar

T = TypeVar("T")


class GeradorRoteirizado:
    """Devolve valores combinados de antemao, e acusa quando acabam.

    `random()` consome a fila de floats; `randint` consome a fila de inteiros,
    conferindo que o valor combinado cabe na faixa pedida — um roteiro que
    devolvesse um nivel fora da faixa do local esconderia o erro do teste em
    vez de revela-lo.
    """

    def __init__(self, floats: Sequence[float] = (), inteiros: Sequence[int] = ()) -> None:
        self.floats = list(floats)
        self.inteiros = list(inteiros)
        self.chamadas: list[str] = []

    def random(self) -> float:
        self.chamadas.append("random")
        if not self.floats:
            raise AssertionError("O roteiro acabou: random() foi chamado a mais.")
        return self.floats.pop(0)

    def randint(self, a: int, b: int) -> int:
        self.chamadas.append(f"randint({a},{b})")
        if not self.inteiros:
            raise AssertionError("O roteiro acabou: randint() foi chamado a mais.")
        valor = self.inteiros.pop(0)
        if not a <= valor <= b:
            raise AssertionError(f"O roteiro deu {valor}, fora da faixa pedida {a}..{b}.")
        return valor

    def choice(self, seq: Sequence[T]) -> T:
        self.chamadas.append("choice")
        return seq[self.randint(0, len(seq) - 1)]


def GeradorSemeado(semente: int) -> Random:  # noqa: N802
    """Um PRNG real semeado, para os testes de determinismo."""
    return Random(semente)
