"""Itens achados em campo depois de uma vitoria (tarefa 7.12 do SDD).

    houve_achado = random() < CHANCE_ITEM_POR_VITORIA
    item         = sorteio por peso em TABELA_DE_ACHADOS
    quantidade   = 1 + (nivel_dificuldade_local // DIFICULDADE_POR_ITEM_EXTRA)

A regra existe para que uma expedicao se pague PARCIALMENTE em Pokebolas. A
conta que fixa os numeros esta em `balance.py`, junto das constantes, e o
resultado dela e: de 0,2 a 0,4 bola devolvida por vitoria contra uma bola
gasta por tentativa de captura. A expedicao cobre de 20% a 35% da propria
mochila — o suficiente para o professor nao sentir que cada despacho e um
prejuizo, e insuficiente para a loja da Fase 8 nascer irrelevante. Um numero
que devolvesse mais bola do que a expedicao consome tornaria a economia
inteira decorativa antes mesmo de existir.

O achado entra no ESTOQUE DO LABORATORIO na resolucao, nunca na carga da
expedicao em curso (regra 18 da spec 007): o treinador ja esta voltando, e uma
Pokebola achada no ultimo encontro nao daria tempo de ser usada.

Duas rolagens, sempre nesta ordem e so depois de uma vitoria: a chance e,
havendo achado, qual item. E o que o plano da spec 007 fixa como passos 6 e 7.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from app.game import balance
from app.game.aleatoriedade import GeradorAleatorio, sortear_indice_por_peso
from app.game.erros import ErroDeDominio


class AchadoInvalido(ErroDeDominio):
    """Os numeros do local nao descrevem um achado possivel."""


@dataclass(frozen=True, slots=True)
class AchadoEmCampo:
    """O que o evento `ITEM` do relatorio registra."""

    item_id: str
    quantidade: int


def quantidade_do_achado(nivel_dificuldade_local: int) -> int:
    """`1 + (nivel_dificuldade // DIFICULDADE_POR_ITEM_EXTRA)`.

    O lugar mais perigoso paga melhor, em degraus: as rotas iniciais dao uma
    unidade, Mt. Moon da duas, e so a dificuldade 8 em diante da tres.
    """
    if nivel_dificuldade_local < 0:
        raise AchadoInvalido(
            f"O nivel de dificuldade do local chegou negativo: {nivel_dificuldade_local}."
        )
    return 1 + nivel_dificuldade_local // balance.DIFICULDADE_POR_ITEM_EXTRA


def achado_apos_vitoria(
    nivel_dificuldade_local: int, gerador: GeradorAleatorio
) -> AchadoEmCampo | None:
    """O item encontrado nesta vitoria, ou None quando nao houve achado.

    A comparacao corre em `Fraction`: `Fraction(valor)` e a representacao exata
    do float que o gerador devolveu, e a constante entra por `str` para que
    0,25 seja 1/4 e nao a aproximacao binaria. Sem isso, calibrar a chance na
    Fase 9 poderia mover o resultado de uma semente ja gravada por conta de um
    arredondamento, e nao por conta da regra.

    A rolagem da chance acontece SEMPRE, mesmo que a tabela de achados fosse
    esvaziada pela calibragem: a ordem das rolagens e contrato.
    """
    if gerador.random() >= Fraction(str(balance.CHANCE_ITEM_POR_VITORIA)):
        return None
    pesos = [peso for _, peso in balance.TABELA_DE_ACHADOS]
    indice = sortear_indice_por_peso(pesos, gerador)
    item_id, _ = balance.TABELA_DE_ACHADOS[indice]
    return AchadoEmCampo(item_id=item_id, quantidade=quantidade_do_achado(nivel_dificuldade_local))
