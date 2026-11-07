"""Sorteio dos encontros de uma expedicao (SDD 4.5).

    qtd_encontros = max(ENCONTROS_MINIMOS, encontros_base + randint(-V, +V))
    especie       = sorteio por peso na tabela LocalEncontro do destino
    nivel         = randint(nivel_min, nivel_max) da linha sorteada

Duas decisoes valem o comentario.

**A ordem das linhas e parte do resultado.** O sorteio acumula os pesos na
ordem em que as linhas chegam, e a mesma semente com as linhas em outra ordem
escolhe outra especie. A ordem canonica do PokeLab e `especie_id` CRESCENTE, e
montar essa lista e responsabilidade de quem constroi o contexto de resolucao
— o repositorio ordena no `ORDER BY`, nunca itera um `dict` nem um `set`.
`ordenar_linhas` esta aqui para quem nao tiver essa garantia; chamar duas vezes
nao muda nada.

**A quantidade de encontros vem do destino, nao da duracao.** Ritmo da sessao e
rendimento da expedicao sao decisoes separadas (SDD 4.5): Pallet Town rende 2
encontros porque e o quintal de casa, nao porque fica perto.

O gerador chega semeado como parametro, como manda o Artigo III, e cada funcao
daqui consome exatamente uma rolagem — a ordem das chamadas e contrato fixado
no plano da spec 007.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.game import balance
from app.game.aleatoriedade import GeradorAleatorio, sortear_indice_por_peso
from app.game.erros import ErroDeDominio, NivelInvalido, SorteioInvalido
from app.game.experience import NIVEL_MINIMO


class EncontroInvalido(ErroDeDominio):
    """Os numeros do encontro nao descrevem uma tabela possivel."""


# --- Entrada ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LinhaDeEncontro:
    """Uma linha de `LocalEncontro` (SDD 3.1), como o dominio precisa ve-la.

    A validacao acontece na construcao porque uma faixa invertida ou um peso
    negativo sao seed errado, nao jogada possivel.
    """

    especie_id: int
    peso: int
    nivel_min: int
    nivel_max: int

    def __post_init__(self) -> None:
        if self.peso < 0:
            raise EncontroInvalido(
                f"A especie {self.especie_id} tem peso negativo na tabela: {self.peso}."
            )
        if self.nivel_min < NIVEL_MINIMO or self.nivel_max > balance.NIVEL_MAXIMO:
            raise NivelInvalido(
                f"A especie {self.especie_id} tem faixa de nivel fora de "
                f"{NIVEL_MINIMO} a {balance.NIVEL_MAXIMO}: "
                f"{self.nivel_min} a {self.nivel_max}."
            )
        if self.nivel_min > self.nivel_max:
            raise EncontroInvalido(
                f"A especie {self.especie_id} tem a faixa de nivel invertida: "
                f"{self.nivel_min} a {self.nivel_max}."
            )


def ordenar_linhas(linhas: Iterable[LinhaDeEncontro]) -> tuple[LinhaDeEncontro, ...]:
    """Poe a tabela na ordem canonica: `especie_id` crescente.

    Existe para quem monta o contexto a partir de uma fonte sem ordem garantida.
    Duas especies iguais na mesma tabela sao seed errado e nao sao tratadas
    aqui — o sorteio funciona, mas a Pokedex registraria a mesma especie duas
    vezes com pesos diferentes.
    """
    return tuple(sorted(linhas, key=lambda linha: linha.especie_id))


# --- Sorteios (ordem fixada no plano da spec 007) ---------------------------


def quantidade_de_encontros(encontros_base: int, gerador: GeradorAleatorio) -> int:
    """`max(ENCONTROS_MINIMOS, encontros_base + randint(-V, +V))`.

    E a PRIMEIRA rolagem da resolucao, antes de qualquer encontro. Um destino
    com `encontros_base` zero ainda rende `ENCONTROS_MINIMOS`: uma expedicao
    que nao encontra nada nao tem relatorio para contar.
    """
    if encontros_base < 0:
        raise EncontroInvalido(
            f"O destino declara uma quantidade negativa de encontros: {encontros_base}."
        )
    variacao = gerador.randint(-balance.VARIACAO_ENCONTROS, balance.VARIACAO_ENCONTROS)
    return max(balance.ENCONTROS_MINIMOS, encontros_base + variacao)


def sortear_especie(
    linhas_de_encontro: Sequence[LinhaDeEncontro], gerador: GeradorAleatorio
) -> LinhaDeEncontro:
    """A linha sorteada pelo peso, na ordem em que as linhas chegaram.

    Tabela vazia ou com peso total zero levanta `SorteioInvalido`, em vez de
    devolver `None`. Foi decisao: um local sem tabela de encontros nao e um
    destino de expedicao possivel, e devolver nada empurraria o problema para
    o laco de resolucao, que produziria uma expedicao de zero eventos sem
    explicar ao professor por que o relatorio veio vazio. Seed quebrado tem de
    doer no seed.
    """
    indice = sortear_indice_por_peso([linha.peso for linha in linhas_de_encontro], gerador)
    return linhas_de_encontro[indice]


def sortear_nivel(linha: LinhaDeEncontro, gerador: GeradorAleatorio) -> int:
    """O nivel do selvagem, na faixa da linha, com os dois extremos incluidos.

    Consome uma rolagem mesmo quando a faixa tem um nivel so, porque a ordem
    das rolagens e contrato: pular a chamada dessincronizaria toda semente ja
    gravada no banco.
    """
    return gerador.randint(linha.nivel_min, linha.nivel_max)


__all__ = [
    "EncontroInvalido",
    "LinhaDeEncontro",
    "SorteioInvalido",
    "ordenar_linhas",
    "quantidade_de_encontros",
    "sortear_especie",
    "sortear_nivel",
]
