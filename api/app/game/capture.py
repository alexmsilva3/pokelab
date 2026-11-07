"""Captura: probabilidade e espaco na bagagem (SDD 4.6).

    p_captura = clamp(
        (taxa_captura / TAXA_CAPTURA_MAXIMA)
      * multiplicador_bola
      * (1 + (nivel_time_medio - nivel_selvagem) * BONUS_CAPTURA_POR_NIVEL)
      * FATOR_CAPTURA,
        P_CAPTURA_MINIMA, P_CAPTURA_MAXIMA)

    slots_de_captura = min(pokebolas_na_carga, capacidade_bagagem(tamanho_do_time))

O `slots_de_captura` e o TETO da expedicao, calculado sobre a carga INICIAL, e
nao a guarda do laco de resolucao: la os dois limites da regra 10 da spec 007
sao checados em separado, e a propria funcao explica por que.

**O terceiro fator pode ficar negativo, e o clamp e quem resolve.** Com
`BONUS_CAPTURA_POR_NIVEL = 0.02`, um time 50 niveis abaixo do selvagem zera o
fator e qualquer diferenca maior o torna negativo — negativo vezes positivo da
negativo, e sem o piso a conta devolveria probabilidade negativa.

A pergunta de design e se o piso de 5% e mesmo o que se quer ali, e a resposta
e sim, pelos mesmos dois motivos de `P_VITORIA_MINIMA`. Primeiro, porque o
piso torna a funcao monotona de novo: tudo que esta 50 ou mais niveis abaixo
cai exatamente no piso, e nao ha faixa em que afundar o time melhore a
captura. Segundo, porque o jogo nunca deve ficar sem historia — um treinador
nivel 5 que tropeca num selvagem de nivel 60 e vence mesmo assim merece a
chance remota de levar o bicho para casa, e "remota" e exatamente o que 5%
significa. O caso e raro por construcao: a mesma diferenca de nivel ja cobra o
seu preco na `p_vitoria`, e sem vitoria nem se tenta capturar.

A alternativa descartada foi limitar o fator de nivel em zero antes da
multiplicacao, o que daria p_captura zero e nenhuma captura possivel. Ela
contraria a formula do SDD 4.6, que manda limitar o produto, e trocaria um
piso explicito por um zero silencioso.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from fractions import Fraction

from app.game import balance
from app.game.erros import NivelInvalido, TaxaDeCapturaInvalida
from app.game.experience import NIVEL_MINIMO
from app.game.itens import CategoriaDeItem, ItemDaMochila, da_categoria
from app.game.team import capacidade_bagagem

NivelMedio = int | float | Fraction


# --- Invariantes (Artigo VI) ------------------------------------------------


def _exigir_taxa_valida(taxa_captura: int) -> None:
    if taxa_captura < 0 or taxa_captura > balance.TAXA_CAPTURA_MAXIMA:
        raise TaxaDeCapturaInvalida(
            f"A taxa de captura {taxa_captura} esta fora da faixa do seed, de 0 a "
            f"{balance.TAXA_CAPTURA_MAXIMA}."
        )


def _exigir_multiplicador_valido(multiplicador_bola: float) -> None:
    if multiplicador_bola <= 0:
        raise TaxaDeCapturaInvalida(
            f"O multiplicador da Pokebola precisa ser positivo: {multiplicador_bola}."
        )


def _exigir_nivel_valido(nivel: NivelMedio, nome: str) -> None:
    """Invariante 7 do SDD 3.3, aceitando media fracionaria de time."""
    if nivel < NIVEL_MINIMO or nivel > balance.NIVEL_MAXIMO:
        raise NivelInvalido(
            f"{nome} {nivel} fora da faixa valida de {NIVEL_MINIMO} a {balance.NIVEL_MAXIMO}."
        )


# --- Formulas ---------------------------------------------------------------


def _fracao(valor: NivelMedio) -> Fraction:
    """`Fraction(str(0.02))` da 1/50; `Fraction(0.02)` daria a aproximacao binaria.

    Mesma decisao de `power.py` e de `expedition.py`: a conta corre exata para
    que a calibragem da Fase 9 nao mude um arredondamento por efeito colateral.
    """
    if isinstance(valor, Fraction):
        return valor
    return Fraction(str(valor))


def _limitar(chance: Fraction) -> float:
    """Clamp antes do arredondamento, nunca depois.

    Arredondar primeiro poderia empurrar 0,04999 para dentro da faixa por
    acidente, e o limite deixaria de ser limite. Mesma ordem de
    `expedition._limitar`, e a mesma precisao: a chance de captura e gravada no
    payload do evento ao lado da chance de vitoria.
    """
    limitada = min(
        max(chance, _fracao(balance.P_CAPTURA_MINIMA)), _fracao(balance.P_CAPTURA_MAXIMA)
    )
    escala = 10**balance.CASAS_DECIMAIS_CHANCE
    return round(limitada * escala) / escala


def nivel_medio_do_time(niveis: Iterable[int]) -> Fraction:
    """A media exata dos niveis do time, que e o que a formula compara.

    Racional e nao float pelo mesmo motivo de `LocalDaExpedicao`: um time de
    niveis 5, 6 e 8 tem media 19/3, e arredondar para 6 antes da subtracao
    moveria a chance de captura da expedicao inteira.

    Time vazio levanta, e nao devolve zero: expedicao exige time (invariante
    17), e uma media de time vazio so poderia chegar aqui por chamada errada.
    """
    valores = tuple(niveis)
    if not valores:
        raise NivelInvalido("Um time vazio nao tem nivel medio, e nao sai em expedicao.")
    for nivel in valores:
        _exigir_nivel_valido(nivel, "Nivel do Pokemon do time")
    return Fraction(sum(valores), len(valores))


def probabilidade_de_captura(
    taxa_captura: int,
    multiplicador_bola: float,
    nivel_time_medio: NivelMedio,
    nivel_selvagem: int,
) -> float:
    """A formula do SDD 4.6, achatada entre P_CAPTURA_MINIMA e P_CAPTURA_MAXIMA.

    `taxa_captura` e `multiplicador_bola` vem do seed: a taxa da especie
    (3 a 255) e a potencia da Pokebola (1.0, 1.5 ou 2.0).
    """
    _exigir_taxa_valida(taxa_captura)
    _exigir_multiplicador_valido(multiplicador_bola)
    _exigir_nivel_valido(nivel_time_medio, "Nivel medio do time")
    _exigir_nivel_valido(nivel_selvagem, "Nivel do selvagem")

    base = Fraction(taxa_captura, balance.TAXA_CAPTURA_MAXIMA)
    diferenca = _fracao(nivel_time_medio) - nivel_selvagem
    vantagem = 1 + diferenca * _fracao(balance.BONUS_CAPTURA_POR_NIVEL)
    bruta = base * _fracao(multiplicador_bola) * vantagem * _fracao(balance.FATOR_CAPTURA)
    return _limitar(bruta)


def slots_de_captura(pokebolas_na_carga: int, tamanho_do_time: int) -> int:
    """O TETO de capturas da expedicao inteira, a partir da carga INICIAL (SDD 4.6).

    E o menor entre as bolas que partiram e o espaco na bagagem. Sem bola, zero
    — e o treinador segue registrando na Pokedex, que e o ponto do criterio 8
    da spec 007.

    **Numero da previa, nao guarda do laco.** Ela responde "quantas capturas
    esta expedicao rende NO TOTAL" e so faz sentido com a carga como ela
    partiu. Chama-la de dentro do laco de `expedition.resolver`, com a carga ja
    decrementada a cada arremesso, e compara-la com as capturas ja feitas
    desconta a bola gasta DUAS vezes — uma dentro do minimo e outra na
    comparacao — e a ultima bola nunca e arremessada. Foi exatamente esse o bug
    da Fase 7. No laco, os dois limites da regra 10 da spec 007 andam
    separados, porque sao grandezas diferentes: a municao e
    `escolher_pokebola(carga) is not None`, e a vaga e
    `len(capturas) < capacidade_bagagem(tamanho_do_time)`.

    Mantida sem chamador em producao porque e formula nomeada do SDD 4.6 e da
    tarefa 7.3 — o numero que a previa de despacho e a calibragem da Fase 9
    exibem —, e porque remove-la pediria mexer no SDD, que esta certo. O que
    estava errado era o uso.

    A capacidade vem de `team.capacidade_bagagem`, nao de uma conta repetida
    aqui: o invariante 11 tem um dono so, e dois lugares subtraindo
    `CAPACIDADE_TOTAL_TREINADOR` divergiriam no dia em que o time crescesse.
    """
    if pokebolas_na_carga < 0:
        raise TaxaDeCapturaInvalida(f"A carga de Pokebolas chegou negativa: {pokebolas_na_carga}.")
    return min(pokebolas_na_carga, capacidade_bagagem(tamanho_do_time))


def contar_pokebolas(carga: Iterable[ItemDaMochila]) -> int:
    """Quantas Pokebolas de qualquer tipo ainda restam na mochila.

    Nome diferente do parametro `pokebolas_na_carga` de `slots_de_captura` de
    proposito: um e a contagem, o outro e o numero ja contado, e dois nomes
    iguais no mesmo modulo viram sombra e depois viram bug.

    E a contagem que alimenta `slots_de_captura`, e herda a mesma ressalva: ela
    e da previa, sobre a carga inicial. Quem precisa saber se ainda ha bola
    AGORA pergunta a `escolher_pokebola`, que devolve None quando acabaram —
    contar para comparar com um limite e o caminho que leva a descontar o
    consumo duas vezes.
    """
    return sum(item.quantidade for item in da_categoria(carga, CategoriaDeItem.POKEBOLA))


def escolher_pokebola(carga: Sequence[ItemDaMochila]) -> ItemDaMochila | None:
    """A Pokebola que o treinador usa no proximo arremesso, ou None se acabaram.

    Escolhe a de MENOR potencia disponivel, pelo mesmo motivo de
    `cura.escolher_cura`: queimar uma Ultra Ball num Rattata e desperdicio, e o
    professor nao esta em campo para impedir. Empate de potencia desempata pelo
    `item_id`, para que a escolha nao dependa da ordem em que o servico montou
    a carga — o Artigo III nao sobrevive a um criterio de desempate instavel.

    Nao sorteia nada de proposito: a ordem das rolagens e contrato (plano da
    spec 007), e uma escolha de bola que consumisse o gerador deslocaria todos
    os sorteios seguintes.
    """
    disponiveis = da_categoria(carga, CategoriaDeItem.POKEBOLA)
    if not disponiveis:
        return None
    return min(disponiveis, key=lambda item: (item.potencia, item.item_id))
