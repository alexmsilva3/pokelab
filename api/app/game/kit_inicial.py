"""Kit inicial do laboratorio (spec 002, regras 7 a 9).

Esta funcao nao cria nada: ela descreve o que precisa existir para o professor
conseguir despachar a primeira expedicao. Quem persiste e `services/`, numa
transacao so (Artigo VII). O dominio apenas responde "o laboratorio nasce
assim", e responde sempre a mesma coisa para o mesmo gerador semeado.

O treinador inicial chega sem time, de proposito: montar o time e a primeira
decisao de jogo do professor, e nao algo que o registro resolve por ele.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.game import balance
from app.game.aleatoriedade import GeradorAleatorio
from app.game.erros import KitInicialInvalido
from app.game.experience import experiencia_total_para_nivel
from app.game.trainers import TreinadorGerado, gerar_treinador

# --- Entrada ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EspecieInicial:
    """O minimo que o dominio precisa saber de uma especie inicial.

    Dataclass enxuta em vez do modelo ORM: o Artigo I nao sobreviveria a um
    `PokemonEspecie` do SQLAlchemy atravessando esta fronteira.
    """

    id: int
    nome: str
    curva_crescimento: str


# --- Saida -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PokemonInicial:
    especie_id: int
    nivel: int
    experiencia: int


@dataclass(frozen=True, slots=True)
class ItemInicial:
    item_id: str
    quantidade: int


@dataclass(frozen=True, slots=True)
class EntradaPokedexInicial:
    especie_id: int
    visto: bool
    capturado: bool


@dataclass(frozen=True, slots=True)
class KitInicial:
    """Descricao completa do estado que o registro materializa."""

    pokemon: tuple[PokemonInicial, ...]
    treinadores: tuple[TreinadorGerado, ...]
    itens: tuple[ItemInicial, ...]
    locais_desbloqueados: tuple[str, ...]
    pokedex: tuple[EntradaPokedexInicial, ...]


# --- Montagem --------------------------------------------------------------


def _validar_especies(especies: Sequence[EspecieInicial]) -> list[EspecieInicial]:
    """Artigo VI: o kit so aceita exatamente as especies iniciais do balance."""
    por_id = {especie.id: especie for especie in especies}
    if len(por_id) != len(especies):
        raise KitInicialInvalido("Ha especies repetidas na lista de iniciais.")

    esperados = set(balance.STARTER_SPECIES_IDS)
    if set(por_id) != esperados:
        recebidos = ", ".join(str(especie_id) for especie_id in sorted(por_id)) or "nenhuma"
        pedidos = ", ".join(str(especie_id) for especie_id in balance.STARTER_SPECIES_IDS)
        raise KitInicialInvalido(
            f"O kit inicial exige exatamente as especies {pedidos}; recebidas: {recebidos}."
        )
    # A ordem de saida segue STARTER_SPECIES_IDS, e nao a ordem de chegada:
    # dois registros com o mesmo seed tem de produzir o mesmo kit (Artigo III).
    return [por_id[especie_id] for especie_id in balance.STARTER_SPECIES_IDS]


def _montar_itens() -> tuple[ItemInicial, ...]:
    """Invariante 9: estoque nunca negativo, nem no instante em que nasce."""
    itens: list[ItemInicial] = []
    for item_id, quantidade in sorted(balance.ESTOQUE_INICIAL.items()):
        if quantidade < 0:
            raise KitInicialInvalido(
                f"Estoque inicial negativo para o item {item_id!r}: {quantidade}."
            )
        itens.append(ItemInicial(item_id=item_id, quantidade=quantidade))
    return tuple(itens)


def _montar_treinadores(rng: GeradorAleatorio) -> tuple[TreinadorGerado, ...]:
    if balance.TREINADORES_NO_KIT_INICIAL < 0:
        raise KitInicialInvalido(
            f"Numero de treinadores iniciais invalido: {balance.TREINADORES_NO_KIT_INICIAL}."
        )
    return tuple(gerar_treinador(rng) for _ in range(balance.TREINADORES_NO_KIT_INICIAL))


def montar_kit_inicial(especies: Sequence[EspecieInicial], rng: GeradorAleatorio) -> KitInicial:
    """Descreve o kit de um laboratorio recem-criado.

    `especies` sao as tres especies iniciais ja lidas do banco pelo servico.
    `rng` e um gerador semeado: o mesmo seed devolve o mesmo kit, nome de
    treinador incluso.
    """
    iniciais = _validar_especies(especies)

    pokemon = tuple(
        PokemonInicial(
            especie_id=especie.id,
            nivel=balance.STARTER_LEVEL,
            experiencia=experiencia_total_para_nivel(
                especie.curva_crescimento, balance.STARTER_LEVEL
            ),
        )
        for especie in iniciais
    )

    pokedex = tuple(
        EntradaPokedexInicial(especie_id=especie.id, visto=True, capturado=True)
        for especie in iniciais
    )

    return KitInicial(
        pokemon=pokemon,
        treinadores=_montar_treinadores(rng),
        itens=_montar_itens(),
        locais_desbloqueados=(balance.LOCAL_INICIAL_ID,),
        pokedex=pokedex,
    )
