"""Contrato do gerador de aleatoriedade.

Artigo III: o dominio nunca cria o proprio gerador — ele chega semeado como
parametro, vindo do campo `seed` da expedicao ou do servico que o construiu.

O protocolo existe porque app/game/ nao pode nem importar `random` para efeito
de anotacao de tipo (o teste constitucional barra o import). Um `random.Random`
satisfaz esta interface estruturalmente, e um gerador falso de teste tambem.
"""

from collections.abc import Sequence
from typing import Protocol, TypeVar

T = TypeVar("T")


class GeradorAleatorio(Protocol):
    """Subconjunto de `random.Random` que o dominio tem permissao de usar."""

    def random(self) -> float:
        """Float em [0.0, 1.0)."""
        ...

    def randint(self, a: int, b: int) -> int:
        """Inteiro em [a, b], com os dois extremos incluidos."""
        ...

    def choice(self, seq: Sequence[T]) -> T:
        """Um elemento da sequencia."""
        ...
