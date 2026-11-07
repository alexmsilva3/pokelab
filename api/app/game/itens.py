"""O item do seed como o dominio o ve em campo (SDD 3.1).

Dois modulos precisam da mesma leitura da mochila — `capture.py` escolhe a
Pokebola e `cura.py` escolhe o remedio —, e tres dataclasses diferentes para a
mesma linha de `ExpedicaoItem` divergiriam na primeira mudanca de seed. Por
isso a mochila mora aqui.

`potencia` tem significado diferente por categoria, e isso vem do seed, nao
desta camada:

    POKEBOLA  multiplicador de captura: Poke Ball 1.0, Great 1.5, Ultra 2.0
    CURA      pontos de hp_atual_pct devolvidos: Potion 20, Super Potion 50
    REVIVE    pontos de hp_atual_pct com que o nocauteado volta: Revive 50

A `quantidade` e o que RESTA na carga no momento do encontro, nao o que partiu:
o consumo em campo e debitado da carga da expedicao, nunca do estoque do
laboratorio (regra 17 da spec 007).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum

from app.game.erros import ItemInvalido


class CategoriaDeItem(StrEnum):
    """As tres categorias que o seed declara em `data/seed/items.json`."""

    POKEBOLA = "POKEBOLA"
    CURA = "CURA"
    REVIVE = "REVIVE"


def categoria_de(valor: str | CategoriaDeItem) -> CategoriaDeItem:
    """Converte o texto gravado na coluna em categoria, recusando o que nao reconhece."""
    try:
        return CategoriaDeItem(valor)
    except ValueError:
        nomes = ", ".join(categoria.value for categoria in CategoriaDeItem)
        raise ItemInvalido(
            f"Categoria de item desconhecida: {valor!r}. Esperado uma de: {nomes}."
        ) from None


@dataclass(frozen=True, slots=True)
class ItemDaMochila:
    """Uma linha da carga da expedicao, com o que ainda resta dela.

    A validacao acontece na construcao: uma carga com quantidade negativa nao e
    jogada possivel, e errar cedo mostra o problema em vez de produzir um
    relatorio plausivel e errado.
    """

    item_id: str
    nome: str
    categoria: CategoriaDeItem
    potencia: float
    quantidade: int

    def __post_init__(self) -> None:
        if self.quantidade < 0:
            raise ItemInvalido(f"A carga de {self.item_id!r} chegou negativa: {self.quantidade}.")
        if self.potencia < 0:
            raise ItemInvalido(f"A potencia de {self.item_id!r} e negativa: {self.potencia}.")

    @property
    def disponivel(self) -> bool:
        """Se ainda ha unidade deste item para gastar."""
        return self.quantidade > 0

    @property
    def potencia_em_pontos(self) -> int:
        """A potencia lida como pontos de `hp_atual_pct`, para CURA e REVIVE.

        O seed guarda `potencia` como float porque a Pokebola a usa como
        multiplicador (1.0, 1.5, 2.0). Um remedio com potencia fracionaria nao
        existe — `hp_atual_pct` e contador inteiro de 0 a 100 — e meio ponto
        de cura seria arredondado em algum lugar sem ninguem decidir onde.
        Por isso a conversao recusa em vez de truncar.
        """
        if self.potencia != int(self.potencia):
            raise ItemInvalido(
                f"O item {self.item_id!r} cura {self.potencia} pontos, e hp_atual_pct so "
                "aceita pontos inteiros."
            )
        return int(self.potencia)


def consumir(
    carga: Sequence[ItemDaMochila], item_id: str, quantidade: int = 1
) -> tuple[ItemDaMochila, ...]:
    """Debita unidades de um item da carga, preservando a ordem das linhas.

    A ordem e preservada porque ela alimenta sorteios e escolhas deterministas
    mais adiante; reconstruir a carga a partir de um `dict` deixaria o Artigo
    III na mao da ordem de insercao de outra pessoa.
    """
    encontrado = False
    nova: list[ItemDaMochila] = []
    for item in carga:
        if item.item_id != item_id:
            nova.append(item)
            continue
        encontrado = True
        if item.quantidade < quantidade:
            raise ItemInvalido(
                f"A carga tem {item.quantidade} de {item_id!r} e o consumo pediu {quantidade}."
            )
        nova.append(replace(item, quantidade=item.quantidade - quantidade))
    if not encontrado:
        raise ItemInvalido(f"O item {item_id!r} nao esta na carga desta expedicao.")
    return tuple(nova)


def da_categoria(
    carga: Iterable[ItemDaMochila], categoria: CategoriaDeItem
) -> tuple[ItemDaMochila, ...]:
    """As linhas de uma categoria que ainda tem unidade, na ordem da carga."""
    return tuple(item for item in carga if item.categoria is categoria and item.disponivel)
