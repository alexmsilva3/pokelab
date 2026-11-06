"""Poder de um Pokemon e de um time (SDD 4.3).

    poder_pokemon = nivel * (1 + soma_stats_base / SOMA_STATS_BASE_REFERENCIA)
                          * (hp_atual_pct / 100)
    poder_time    = soma(poder_pokemon) * (1 + nivel_treinador * BONUS_POR_NIVEL_TREINADOR)

A Fase 4 antecipa esta formula da Fase 7 porque a previa de montagem precisa
dela agora: o professor so decide quantos Pokemon dar a cada treinador se vir o
que a escolha produz. A dificuldade do local e a sigmoide de p_vitoria ficam
para a Fase 7, quando houver destino para comparar.

Tres decisoes de implementacao valem o comentario.

A primeira: **o poder e inteiro**. Ele existe para ser lido pelo professor na
hora de montar o time, e "1847" informa tanto quanto "1847.3329" com metade do
ruido. Mais importante, e o mesmo numero que a Fase 7 vai dividir pela
dificuldade: um poder exibido diferente do poder que decide a expedicao seria
um relatorio que nao explica o proprio resultado.

A segunda: a conta inteira corre em `Fraction`, nunca em ponto flutuante, pelo
mesmo motivo de `stats.py` e `experience.py` — a Fase 8 vai mexer em
`BONUS_POR_NIVEL_TREINADOR` e em `SOMA_STATS_BASE_REFERENCIA`, e um
arredondamento que muda conforme a calibragem transformaria o Artigo III em
promessa. `round` sobre `Fraction` desempata para par, de forma exata.

A terceira: o arredondamento acontece **uma vez**, no fim. O poder do time e a
soma exata dos poderes dos Pokemon multiplicada pelo bonus do treinador, e nao
a soma de valores ja arredondados — somar tres arredondamentos erra ate um
ponto e meio antes mesmo do bonus entrar.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from app.game import balance
from app.game.erros import HpAtualInvalido, NivelInvalido, StatInvalido
from app.game.experience import NIVEL_MINIMO
from app.game.stats import StatsBase
from app.game.trainers import exigir_nivel_de_treinador

# --- Entrada ---------------------------------------------------------------


def somar_stats_base(base: StatsBase) -> int:
    """Soma dos seis stats-base da especie, que e o que a formula normaliza."""
    return (
        base.hp
        + base.ataque
        + base.defesa
        + base.ataque_especial
        + base.defesa_especial
        + base.velocidade
    )


@dataclass(frozen=True, slots=True)
class PokemonNoTime:
    """O minimo que o poder precisa saber de um Pokemon do time.

    Dataclass enxuta em vez do modelo ORM, como em `stats.py` e `kit_inicial.py`:
    o Artigo I nao sobreviveria a uma `PokemonInstancia` do SQLAlchemy
    atravessando esta fronteira. Quem le o banco e junta instancia com especie e
    `services/`.
    """

    nivel: int
    soma_stats_base: int
    hp_atual_pct: int

    @classmethod
    def a_partir_dos_stats(cls, base: StatsBase, nivel: int, hp_atual_pct: int) -> PokemonNoTime:
        """Atalho para quem ja tem os seis stats-base em maos."""
        return cls(nivel=nivel, soma_stats_base=somar_stats_base(base), hp_atual_pct=hp_atual_pct)


# --- Invariantes (Artigo VI) ------------------------------------------------


def _exigir_pokemon_valido(pokemon: PokemonNoTime) -> None:
    """Invariante 7 do SDD 3.3, mais as faixas de hp e de stats."""
    if pokemon.nivel < NIVEL_MINIMO or pokemon.nivel > balance.NIVEL_MAXIMO:
        raise NivelInvalido(
            f"Nivel {pokemon.nivel} fora da faixa valida de "
            f"{NIVEL_MINIMO} a {balance.NIVEL_MAXIMO}."
        )
    if pokemon.hp_atual_pct < 0 or pokemon.hp_atual_pct > balance.BASE_PERCENTUAL:
        raise HpAtualInvalido(
            f"hp_atual_pct {pokemon.hp_atual_pct} fora da faixa valida de "
            f"0 a {balance.BASE_PERCENTUAL}."
        )
    if pokemon.soma_stats_base < 0:
        raise StatInvalido(
            f"A soma dos stats base nao pode ser negativa: {pokemon.soma_stats_base}."
        )


# --- Formulas ---------------------------------------------------------------


def _poder_exato(pokemon: PokemonNoTime) -> Fraction:
    """O poder do Pokemon antes do arredondamento, em racional exato."""
    _exigir_pokemon_valido(pokemon)
    bonus_de_stats = 1 + Fraction(pokemon.soma_stats_base, balance.SOMA_STATS_BASE_REFERENCIA)
    saude = Fraction(pokemon.hp_atual_pct, balance.BASE_PERCENTUAL)
    return pokemon.nivel * bonus_de_stats * saude


def _multiplicador_do_treinador(nivel_treinador: int) -> Fraction:
    """1 + nivel * BONUS_POR_NIVEL_TREINADOR.

    `Fraction(str(0.03))` da 3/100; `Fraction(0.03)` daria a aproximacao
    binaria, como ja decidido em `experience.py`.
    """
    exigir_nivel_de_treinador(nivel_treinador)
    return 1 + nivel_treinador * Fraction(str(balance.BONUS_POR_NIVEL_TREINADOR))


def _arredondar(valor: Fraction) -> float:
    """Arredonda para a casa decimal do balance, sem passar por float antes."""
    escala = 10**balance.CASAS_DECIMAIS_PODER
    return round(valor * escala) / escala


def poder_pokemon(pokemon: PokemonNoTime) -> float:
    """Poder individual, para a ficha do Pokemon.

    Um Pokemon nocauteado (hp_atual_pct zero) vale zero: ele esta no time, mas
    nao contribui para a expedicao.

    Mesma precisao do poder do time, para que a soma exibida dos individuos
    nao divirja visivelmente do total.
    """
    return _arredondar(_poder_exato(pokemon))


def poder_do_time(pokemon: Iterable[PokemonNoTime], nivel_treinador: int) -> float:
    """Poder do time ja com o bonus do treinador.

    Time vazio vale zero, e nao e erro: e como todo treinador comeca, e a
    previa precisa saber dizer isso enquanto o professor ainda nao escolheu
    ninguem (regra 10 da spec 004).

    Sai com CASAS_DECIMAIS_PODER casas. Arredondar para inteiro escondia o
    bonus do treinador em times pequenos — tres niveis de treinador diferentes
    davam o mesmo numero, e o criterio de aceite 9 era falso na pratica. A
    conta inteira corre em Fraction e o arredondamento acontece uma unica vez,
    no fim: somar poderes ja arredondados daria um total diferente de
    arredondar a soma.
    """
    multiplicador = _multiplicador_do_treinador(nivel_treinador)
    soma = sum((_poder_exato(membro) for membro in pokemon), Fraction(0))
    return _arredondar(soma * multiplicador)
