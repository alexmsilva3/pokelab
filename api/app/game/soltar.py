"""Soltar um Pokemon: devolver a natureza, de graca (SDD 4.10, spec 008).

E a saida rapida do viveiro, e a unica que nao paga nada — nem moeda, nem
experiencia, nem item. Isso e deliberado e nao e descuido de escopo: se soltar
rendesse moeda, soltar viraria a forma otima de jogar o excedente fora e a
Central de Entregas perderia a razao de existir. A entrega paga porque exige a
especie certa, na quantidade certa, levada ate o lugar certo por um treinador
ocupado durante a viagem; soltar e o contrario disso — e desistir, e desistir
e de graca nos dois sentidos. Por isso este modulo nao devolve recompensa
nenhuma: ele so responde "pode?".

A Pokedex tambem nao e tocada em lugar nenhum daqui. `visto`, `capturado` e os
avistamentos sobrevivem: o professor soltou o bicho, nao desaprendeu o que ele
era. Soltar mexe no acervo vivo, nao no conhecimento.

**As recusas sao distinguiveis de proposito.** "Nao da para soltar" nao e
frase util numa tela; "este Pokemon esta em expedicao com o Kenji" e. Cada uma
carrega `codigo` e `detalhes`, que o servico traduz para o envelope 409 do
contrato, e a previa usa exatamente as mesmas checagens — previa e escrita que
validam por caminhos diferentes divergem no primeiro invariante novo, e o
professor leva um erro no botao que a previa jurava que nao existia.

**`exigir_que_sobre_pokemon` mora aqui e e usada tambem pelo aceite de
entrega.** E a mesma regra — o laboratorio nunca fica com zero —, e duas
copias dela divergiriam no dia em que o aceite passasse a tirar mais de um
Pokemon de uma vez. Por isso ela recebe quantos estao saindo, e nao so o
total.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.game import balance
from app.game.erros import ErroDeDominio
from app.game.trainers import DESCRICAO_DO_STATUS, StatusTreinador
from app.game.viveiro import PokemonDoLaboratorio

# --- Erros (Artigo VI) ------------------------------------------------------


class ErroDeSoltura(ErroDeDominio):
    """Raiz das recusas de soltura.

    O `codigo` e o mesmo do contrato de API, declarado uma vez aqui para que o
    router nao tenha a propria tabela de traducao.
    """

    codigo: ClassVar[str] = "SOLTURA_INVALIDA"

    def __init__(self, mensagem: str, *, detalhes: dict[str, Any] | None = None) -> None:
        self.detalhes = detalhes or {}
        super().__init__(mensagem)


class PokemonEmExpedicao(ErroDeSoltura):
    """Invariante 24: o treinador dele esta em campo, entao ele nao esta aqui.

    Distinto de `PokemonComprometido` apesar de os dois significarem "esta
    fora de alcance": o professor resolve um esperando o relatorio e o outro
    esperando a entrega, e a tela precisa dizer qual.
    """

    codigo: ClassVar[str] = "POKEMON_EM_EXPEDICAO"


class TreinadorEmEntrega(ErroDeSoltura):
    """Invariantes 3 e 4: treinador ocupado nao tem o time alterado.

    Nao e uma quarta regra inventada, e sim a aplicacao de uma que ja existia
    ao unico estado que o SDD 4.10 nao nomeia: o Pokemon que esta no TIME
    PROPRIO de um treinador que saiu em entrega. Ele nao e `comprometido` — os
    comprometidos sao os Pokemon pedidos, que nao estao em time nenhum — mas
    tambem nao esta no laboratorio: viaja com o mensageiro, exatamente como na
    expedicao. Soltar daqui desatribuiria um Pokemon de um treinador ocupado,
    que e o invariante 4 ao contrario.

    O codigo reaproveita `TREINADOR_OCUPADO`, que ja e vocabulario do contrato
    desde a Fase 4, em vez de criar um sexto. O NOME da classe difere de
    `team.TreinadorOcupado` de proposito, pelo mesmo motivo de
    `expedition.TreinadorIndisponivel`: os dois erros convivem no mesmo
    servico, e dois nomes iguais importados de modulos diferentes viram alias
    e depois viram bug.
    """

    codigo: ClassVar[str] = "TREINADOR_OCUPADO"


class PokemonComprometido(ErroDeSoltura):
    """Invariante 24: ja foi prometido a uma entrega e sai por ela, nao daqui."""

    codigo: ClassVar[str] = "POKEMON_COMPROMETIDO"


class UltimoPokemon(ErroDeSoltura):
    """Invariante 25: o laboratorio nunca fica sem nenhum Pokemon.

    Esta e a guarda que impede um beco sem saida PERMANENTE. Sem Pokemon nao
    ha time, sem time nao ha expedicao, sem expedicao nao ha como obter outro,
    e os iniciais sao concedidos uma vez so (invariante 10): essa porta nao
    reabre. Vale igual para a soltura e para o aceite de entrega.
    """

    codigo: ClassVar[str] = "ULTIMO_POKEMON"


class EstadoInconsistente(ErroDeSoltura):
    """O Pokemon e o treinador recebidos nao falam do mesmo vinculo.

    Nao e jogada possivel, e sim chamada errada: o servico buscou o treinador
    errado, ou esqueceu de busca-lo. Levantar aqui mostra o problema no lugar
    onde o dado entrou, em vez de soltar um Pokemon que esta em campo.
    """

    codigo: ClassVar[str] = "ESTADO_INCONSISTENTE"


# --- Entrada ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TreinadorDoPokemon:
    """O treinador a quem o Pokemon pertence, se pertencer a algum."""

    id: UUID
    nome: str
    status: StatusTreinador


# --- Saida ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PreviaDeSoltura:
    """A mesma validacao de `pode_soltar`, com o erro devolvido em vez de levantado.

    Existe para a tela poder desabilitar o botao e dizer por que, no mesmo
    arranjo de `team.prever_time` e `expedition.prever_despacho`.
    """

    permitido: bool
    codigo: str | None = None
    motivo: str | None = None
    detalhes: dict[str, Any] | None = None


# --- A guarda do ultimo Pokemon (invariante 25) -----------------------------


def exigir_que_sobre_pokemon(total_do_laboratorio: int, saindo: int = 1) -> None:
    """O laboratorio nunca fica com menos de `POKEMON_MINIMOS_NO_LABORATORIO`.

    Escrita para ser reusada, e nao copiada: a soltura chama com `saindo=1` e
    o aceite de entrega chama com quantos Pokemon o pedido leva. Uma segunda
    copia desta conta divergiria exatamente no caso que mais importa — a
    entrega que esvazia o laboratorio de uma vez.
    """
    if total_do_laboratorio < 0:
        raise EstadoInconsistente(
            f"O laboratorio nao pode ter um total negativo de Pokemon: {total_do_laboratorio}."
        )
    if saindo < 0:
        raise EstadoInconsistente(f"Nao e possivel tirar {saindo} Pokemon do laboratorio.")
    restantes = total_do_laboratorio - saindo
    if restantes >= balance.POKEMON_MINIMOS_NO_LABORATORIO:
        return
    raise UltimoPokemon(
        "O laboratorio ficaria sem nenhum Pokemon, e sem nenhum nao ha como montar time, "
        "despachar expedicao nem conseguir outro. Guarde ao menos "
        f"{balance.POKEMON_MINIMOS_NO_LABORATORIO}.",
        detalhes={
            "total_do_laboratorio": total_do_laboratorio,
            "saindo": saindo,
            "minimo": balance.POKEMON_MINIMOS_NO_LABORATORIO,
        },
    )


# --- A soltura (invariantes 24 e 25) ----------------------------------------


def _exigir_vinculo_coerente(
    pokemon: PokemonDoLaboratorio, treinador: TreinadorDoPokemon | None
) -> None:
    if treinador is None:
        if pokemon.treinador_id is not None:
            raise EstadoInconsistente(
                f"O Pokemon {pokemon.id} esta no time do treinador {pokemon.treinador_id}, "
                "que nao foi informado."
            )
        return
    if pokemon.treinador_id != treinador.id:
        raise EstadoInconsistente(
            f"O Pokemon {pokemon.id} nao esta no time do treinador {treinador.id}."
        )


def pode_soltar(
    pokemon: PokemonDoLaboratorio,
    treinador: TreinadorDoPokemon | None,
    total_do_laboratorio: int,
) -> None:
    """Devolve None quando a soltura e permitida; levanta a recusa quando nao.

    `treinador` e nulo para quem esta no viveiro, que e o caso comum. Soltar
    do time de um treinador DISPONIVEL ou DESCANSANDO e permitido: o Pokemon
    esta no laboratorio, e o time so encolhe.

    A ordem das checagens e contrato, porque mais de uma pode valer ao mesmo
    tempo — o ultimo Pokemon do laboratorio pode estar em expedicao. Primeiro
    vem as que dizem "ele nao esta aqui para ser solto" (invariantes 24, 3 e
    4), e por ultimo a que diz "ele esta, mas e o unico" (invariante 25). A
    primeira recusa e a que descreve o obstaculo mais imediato.

    Nao devolve ganho nenhum porque soltar nao rende nada (SDD 4.10).
    """
    _exigir_vinculo_coerente(pokemon, treinador)

    if treinador is not None and treinador.status is StatusTreinador.EM_EXPEDICAO:
        raise PokemonEmExpedicao(
            f"Este Pokemon esta em expedicao com {treinador.nome} e so pode ser solto depois "
            "que o relatorio for reclamado.",
            detalhes={
                "pokemon_id": str(pokemon.id),
                "treinador_id": str(treinador.id),
                "treinador_nome": treinador.nome,
                "status_treinador": treinador.status.value,
                "status_descricao": DESCRICAO_DO_STATUS[treinador.status],
            },
        )

    if treinador is not None and treinador.status is StatusTreinador.EM_ENTREGA:
        raise TreinadorEmEntrega(
            f"Este Pokemon esta no time de {treinador.nome}, que saiu em entrega. O time de um "
            "treinador ocupado nao muda ate ele voltar.",
            detalhes={
                "pokemon_id": str(pokemon.id),
                "treinador_id": str(treinador.id),
                "treinador_nome": treinador.nome,
                "status_treinador": treinador.status.value,
                "status_descricao": DESCRICAO_DO_STATUS[treinador.status],
            },
        )

    if pokemon.comprometido_entrega_id is not None:
        raise PokemonComprometido(
            "Este Pokemon ja foi prometido a uma entrega e sai do laboratorio por ela. "
            "Conclua ou aguarde a entrega.",
            detalhes={
                "pokemon_id": str(pokemon.id),
                "entrega_id": str(pokemon.comprometido_entrega_id),
            },
        )

    exigir_que_sobre_pokemon(total_do_laboratorio)


def prever_soltura(
    pokemon: PokemonDoLaboratorio,
    treinador: TreinadorDoPokemon | None,
    total_do_laboratorio: int,
) -> PreviaDeSoltura:
    """`pode_soltar` com o erro devolvido em vez de levantado."""
    try:
        pode_soltar(pokemon, treinador, total_do_laboratorio)
    except ErroDeSoltura as erro:
        return PreviaDeSoltura(
            permitido=False,
            codigo=erro.codigo,
            motivo=str(erro),
            detalhes=erro.detalhes,
        )
    return PreviaDeSoltura(permitido=True)
