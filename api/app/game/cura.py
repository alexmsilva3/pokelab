"""Escolha e efeito do item de cura em campo (SDD 4.5, regras 8 e 9 da spec 007).

Uma derrota desgasta o time em 15 a 30 pontos e consome um item de cura se
houver. Tres derrotas **sem cura disponivel** encerram a expedicao em falha —
consumir um item zera a contagem, porque a regra fala em tres derrotas sem o
que curar.

Quatro decisoes valem o comentario.

**O treinador gasta o mais barato que resolve.** `REVIVE` quando ha alguem
nocauteado, senao a `CURA` de MENOR potencia disponivel. Queimar uma Super
Potion para devolver 20 pontos e desperdicio, e o professor nao esta em campo
para impedir — a escolha e do dominio, e ela e a avarenta.

**Nada aqui sorteia.** A ordem das rolagens e contrato (plano da spec 007), e
uma escolha de item que consumisse o gerador deslocaria todos os sorteios
seguintes da expedicao. Por isso o revive atende o PRIMEIRO nocauteado na
ordem canonica do time, e o desempate entre dois itens de mesma potencia e o
`item_id` — criterio estavel, independente da ordem em que o servico montou a
carga.

**A cura alcanca o time inteiro, nocauteado incluido.** E leitura deliberada
da regra do SDD, e diverge dos jogos de mao, onde uma Potion nao levanta quem
caiu. A questao 8 do SDD ja decidiu que ninguem morre no PokeLab: o Pokemon
nocauteado esta exausto, nao perdido, e o treinador em campo cuida de todos.
O `REVIVE` continua tendo razao de existir e vindo primeiro, porque devolve
50 pontos a quem esta em zero, contra os 20 de uma Potion.

**Nenhum efeito passa de 100** — `hp_atual_pct` e contador inteiro de 0 a 100,
e o excedente da cura e perdido como qualquer excedente.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from app.game import balance
from app.game.itens import CategoriaDeItem, ItemDaMochila, da_categoria
from app.game.power import PokemonNoTime

# --- Escolha ---------------------------------------------------------------


def ha_nocauteado(time: Sequence[PokemonNoTime]) -> bool:
    """Se alguem do time esta em zero por cento (SDD 4.2)."""
    return any(membro.hp_atual_pct == 0 for membro in time)


def ha_o_que_curar(time: Sequence[PokemonNoTime]) -> bool:
    """Se alguem do time esta abaixo de 100 por cento."""
    return any(membro.hp_atual_pct < balance.BASE_PERCENTUAL for membro in time)


def escolher_cura(
    carga_restante: Sequence[ItemDaMochila], time: Sequence[PokemonNoTime]
) -> ItemDaMochila | None:
    """O item que o treinador usa depois de uma derrota, ou None se nao ha.

    `None` significa derrota sem cura, e e o que faz a contagem do invariante
    de falha avancar (regra 9 da spec 007). Ele sai em tres casos: carga sem
    `CURA` nem `REVIVE`, carga com `REVIVE` e ninguem nocauteado para usa-lo, e
    time inteiro ja em 100 por cento.

    O ultimo caso merece nota: com o time cheio de vida nao ha o que curar, e
    gastar uma Potion para nao devolver ponto nenhum seria pior do que contar
    a derrota. Na pratica ele nao acontece depois de uma derrota, que tira de
    15 a 30 pontos antes de a cura ser escolhida; ele existe para que a funcao
    continue correta para quem a chamar de outro ponto.
    """
    if not ha_o_que_curar(time):
        return None

    if ha_nocauteado(time):
        revives = da_categoria(carga_restante, CategoriaDeItem.REVIVE)
        if revives:
            return _mais_barato(revives)

    curas = da_categoria(carga_restante, CategoriaDeItem.CURA)
    if curas:
        return _mais_barato(curas)
    return None


def _mais_barato(itens: Sequence[ItemDaMochila]) -> ItemDaMochila:
    """O de menor potencia, desempatado pelo `item_id` para ser determinista."""
    return min(itens, key=lambda item: (item.potencia, item.item_id))


# --- Efeito -----------------------------------------------------------------


def _somar_pontos(hp_atual_pct: int, pontos: int) -> int:
    """Soma pontos de vida sem passar do teto percentual."""
    return min(balance.BASE_PERCENTUAL, hp_atual_pct + pontos)


def aplicar_cura(item: ItemDaMochila, time: Sequence[PokemonNoTime]) -> tuple[PokemonNoTime, ...]:
    """O time depois do item, na mesma ordem em que chegou.

    `CURA` soma `potencia` pontos a cada membro; `REVIVE` leva UM nocauteado —
    o primeiro na ordem canonica do time — a `potencia` pontos. Um `REVIVE`
    sem ninguem nocauteado devolve o time intacto em vez de levantar: quem
    escolhe o item e `escolher_cura`, que nunca o escolhe nesse caso, e
    derrubar a resolucao inteira por causa de uma chamada ociosa seria trocar
    um desperdicio de item por um erro 500.

    Uma Pokebola chega aqui como chamada errada, nao como jogada: ela nao cura
    nada e o time volta intacto.
    """
    pontos = item.potencia_em_pontos

    if item.categoria is CategoriaDeItem.CURA:
        return tuple(
            replace(membro, hp_atual_pct=_somar_pontos(membro.hp_atual_pct, pontos))
            for membro in time
        )

    if item.categoria is CategoriaDeItem.REVIVE:
        curado = False
        novo: list[PokemonNoTime] = []
        for membro in time:
            if not curado and membro.hp_atual_pct == 0:
                novo.append(replace(membro, hp_atual_pct=_somar_pontos(0, pontos)))
                curado = True
            else:
                novo.append(membro)
        return tuple(novo)

    return tuple(time)
