"""Evolucao por nivel, disparada na resolucao da expedicao (SDD 4.1).

A regra tem uma linha: enquanto a especie tiver `evolui_para_id` e o nivel
alcancado chegar a `evolui_em_nivel`, a especie avanca. O que merece as
decisoes abaixo e o que acontece nas pontas.

**A cadeia encadeia.** A experiencia de uma expedicao inteira e aplicada de uma
vez, e um Bulbasaur que salte do nivel 15 ao 33 passa por Ivysaur (16) e chega
a Venusaur (32) na mesma resolucao. O relatorio recebe dois eventos `EVOLUCAO`,
em ordem, porque as duas coisas aconteceram em campo — esconder a intermediaria
faria a Pokedex do professor pular um registro.

**O catalogo nao e o ORM.** Ele chega como um mapa de `especie_id` para
`EspecieNoCatalogo`, montado por `services/` a partir do seed. O Artigo I nao
sobreviveria a um `PokemonEspecie` do SQLAlchemy atravessando esta fronteira,
como ja vale em `stats.py` e em `power.py`.

**Dado circular levanta, nao gira.** O teto de
`EVOLUCOES_MAXIMAS_POR_EXPEDICAO` existe para que um seed com `evolui_para_id`
apontando de volta nao prenda uma requisicao num laco infinito. Atingir o teto
nao e jogada possivel: e seed invalido, e o dominio diz isso em vez de devolver
uma cadeia truncada que o professor leria como regra do jogo.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.game import balance
from app.game.erros import CatalogoInvalido, NivelInvalido
from app.game.experience import NIVEL_MINIMO

# --- Entrada ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EspecieNoCatalogo:
    """O minimo que a evolucao precisa saber de uma especie do seed.

    `evolui_para_id` e `evolui_em_nivel` andam juntos: uma especie que aponta
    para a seguinte sem dizer em que nivel, ou que diz o nivel sem apontar para
    ninguem, e linha de seed pela metade.
    """

    id: int
    nome: str
    evolui_para_id: int | None = None
    evolui_em_nivel: int | None = None


CatalogoDeEspecies = Mapping[int, EspecieNoCatalogo]


# --- Invariantes (Artigo VI) ------------------------------------------------


def _buscar(especie_id: int, catalogo: CatalogoDeEspecies) -> EspecieNoCatalogo:
    especie = catalogo.get(especie_id)
    if especie is None:
        raise CatalogoInvalido(
            f"A especie {especie_id} nao esta no catalogo recebido, e sem ela nao da para "
            "saber se ela evolui."
        )
    return especie


def _exigir_elo_completo(especie: EspecieNoCatalogo) -> None:
    if especie.evolui_para_id is None:
        return
    if especie.evolui_em_nivel is None:
        raise CatalogoInvalido(
            f"A especie {especie.nome} ({especie.id}) aponta para a evolucao "
            f"{especie.evolui_para_id} sem dizer em que nivel ela acontece."
        )
    if especie.evolui_em_nivel < NIVEL_MINIMO or especie.evolui_em_nivel > balance.NIVEL_MAXIMO:
        raise CatalogoInvalido(
            f"A especie {especie.nome} ({especie.id}) evolui num nivel fora da faixa de "
            f"{NIVEL_MINIMO} a {balance.NIVEL_MAXIMO}: {especie.evolui_em_nivel}."
        )


# --- Regra ------------------------------------------------------------------


def evolucoes_apos(
    especie_atual: int,
    nivel: int,
    catalogo: CatalogoDeEspecies,
) -> tuple[EspecieNoCatalogo, ...]:
    """A cadeia de evolucoes que o nivel alcancado dispara, em ordem.

    Devolve vazio quando nada evolui — que e o caso comum, inclusive para toda
    especie final. O ultimo elemento, quando ha, e a especie que a resolucao
    grava na `PokemonInstancia`; os anteriores existem para o relatorio contar
    a historia inteira.

    A funcao e pura e idempotente: chamada de novo com a especie resultante e o
    mesmo nivel, devolve vazio.
    """
    if nivel < NIVEL_MINIMO or nivel > balance.NIVEL_MAXIMO:
        raise NivelInvalido(
            f"Nivel {nivel} fora da faixa valida de {NIVEL_MINIMO} a {balance.NIVEL_MAXIMO}."
        )

    cadeia: list[EspecieNoCatalogo] = []
    especie = _buscar(especie_atual, catalogo)
    while True:
        _exigir_elo_completo(especie)
        if especie.evolui_para_id is None or especie.evolui_em_nivel is None:
            return tuple(cadeia)
        if nivel < especie.evolui_em_nivel:
            return tuple(cadeia)
        if len(cadeia) >= balance.EVOLUCOES_MAXIMAS_POR_EXPEDICAO:
            caminho = " -> ".join(elo.nome for elo in cadeia)
            raise CatalogoInvalido(
                f"A cadeia de evolucao de {especie_atual} passou de "
                f"{balance.EVOLUCOES_MAXIMAS_POR_EXPEDICAO} etapas ({caminho}): o catalogo "
                "tem um ciclo ou uma linha evolutiva impossivel."
            )
        especie = _buscar(especie.evolui_para_id, catalogo)
        cadeia.append(especie)
