"""Contrato do gerador de aleatoriedade.

Artigo III: o dominio nunca cria o proprio gerador — ele chega semeado como
parametro, vindo do campo `seed` da expedicao ou do servico que o construiu.

O protocolo existe porque app/game/ nao pode nem importar `random` para efeito
de anotacao de tipo (o teste constitucional barra o import). Um `random.Random`
satisfaz esta interface estruturalmente, e um gerador falso de teste tambem.

Mora aqui tambem o sorteio por peso, que e a unica rolagem usada por mais de um
modulo (encontros e achados de item). Ele esta neste modulo, e nao duplicado
nos dois, porque a forma do sorteio e contrato do Artigo III: duas
implementacoes dariam resultados diferentes para a mesma semente no dia em que
uma delas fosse "melhorada".
"""

from collections.abc import Sequence
from fractions import Fraction
from typing import Protocol, TypeVar

from app.game.erros import SorteioInvalido

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


def sortear_indice_por_peso(pesos: Sequence[int], gerador: GeradorAleatorio) -> int:
    """Indice sorteado proporcionalmente ao peso, na ordem em que os pesos chegam.

    O algoritmo e o acumulado simples:

        alvo = gerador.random() * peso_total
        devolve o primeiro indice cujo acumulado SUPERA o alvo

    Tres decisoes valem o comentario.

    **A ordem da sequencia e parte do resultado.** Com os mesmos pesos em outra
    ordem, a mesma semente escolhe outro item. Por isso quem monta a tabela e
    responsavel por uma ordem canonica e estavel — para a tabela de encontros,
    `especie_id` crescente; para os achados, a ordem declarada em
    `balance.TABELA_DE_ACHADOS`. Nunca itere um `dict` montado em runtime nem
    um `set` para alimentar esta funcao.

    **Uma chamada de `random()` por sorteio, sempre.** A ordem das rolagens e
    contrato (plano da spec 007) e um atalho que evitasse a chamada quando ha
    uma unica linha dessincronizaria toda semente gravada.

    **A comparacao corre em `Fraction`.** `Fraction(valor)` e a representacao
    binaria exata do float que o gerador devolveu, e multiplicar por um inteiro
    e exato: o indice escolhido nao depende do arredondamento do produto em
    ponto flutuante. Na borda, `alvo` igual a um acumulado cai no indice
    seguinte — a faixa de cada indice e fechada embaixo e aberta em cima.
    """
    if not pesos:
        raise SorteioInvalido("Nao ha linha nenhuma para sortear: a tabela chegou vazia.")
    for indice, peso in enumerate(pesos):
        if peso < 0:
            raise SorteioInvalido(f"O peso da linha {indice} e negativo: {peso}.")
    peso_total = sum(pesos)
    if peso_total == 0:
        raise SorteioInvalido("A soma dos pesos da tabela e zero: nenhuma linha pode ser sorteada.")

    alvo = Fraction(gerador.random()) * peso_total
    acumulado = 0
    for indice, peso in enumerate(pesos):
        acumulado += peso
        if alvo < acumulado:
            return indice
    # `random()` devolve [0.0, 1.0), entao alvo < peso_total e o laco sempre
    # devolve. Esta linha so e alcancavel com um gerador falso fora do
    # contrato, e devolver a ultima linha e melhor do que estourar por indice.
    return len(pesos) - 1
