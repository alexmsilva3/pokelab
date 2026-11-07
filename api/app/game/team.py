"""Composicao do time de um treinador (spec 004, regras 2 a 7 e 11).

Este modulo e a primeira linha de defesa dos invariantes do SDD 3.3 que falam
de time (Artigo VI):

    1  um treinador tem no maximo TAMANHO_MAXIMO_TIME Pokemon
    2  um Pokemon pertence a no maximo um treinador por vez
    3  treinador ocupado (EM_EXPEDICAO ou EM_ENTREGA) nao tem o time alterado
    4  Pokemon de treinador ocupado nao e desatribuido
    11 treinador carrega CAPACIDADE_TOTAL_TREINADOR Pokemon: time mais bagagem
    14 Pokemon comprometido com entrega nao entra em time

Os invariantes 5 e 6 do SDD nao passam por aqui: o limite de treinadores do
laboratorio vive em `laboratorio.limite_treinadores`, e a vizinhanca do destino
de expedicao e da Fase 6.

A escrita e de substituicao total: quem chama manda o time que deve existir ao
final, e o dominio devolve o que entra e o que sai. Isso elimina a classe
inteira de bugs de "adicionar e remover" — ordem de operacoes, estado
intermediario invalido, dois cliques concorrentes deixando quatro Pokemon no
time.

Duas decisoes de desenho valem o comentario.

A primeira: **a previa e o salvamento chamam a mesma funcao**. `prever_time` e
`validar_time` com o erro capturado em vez de propagado. Se fossem duas
validacoes, a previa aceitaria o que o salvamento recusa e o professor levaria
um erro no botao — exatamente o que a previa existe para evitar.

A segunda: **os erros sao distinguiveis**. A previa mostra o motivo enquanto o
professor monta, e "este Pokemon ja esta com outro treinador" e uma frase util,
enquanto "composicao invalida" nao e. Cada erro carrega `codigo` e `detalhes`,
que a camada de servico traduz para o envelope 409 do contrato.

Nada aqui consulta o banco: quem busca e passa o estado e `services/`. A lista
`pokemon_conhecidos` deve conter ao menos os Pokemon pedidos e os que hoje
estao no time do treinador — e o que permite calcular quem sai sem uma segunda
consulta. Qualquer id pedido fora dessa lista e tratado como inexistente, e e
assim que o escopo de laboratorio (regra 11 da spec) chega ate aqui: o servico
so carrega Pokemon do laboratorio do professor.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.game import balance
from app.game.erros import ErroDeDominio
from app.game.trainers import DESCRICAO_DO_STATUS, StatusTreinador

# --- Erros (Artigo VI) ------------------------------------------------------


class ErroDeTime(ErroDeDominio):
    """Raiz das recusas de composicao de time.

    O `codigo` e o mesmo do contrato de API, declarado uma vez aqui para que o
    router nao tenha a propria tabela de traducao e as duas possam divergir.
    """

    codigo: ClassVar[str] = "TIME_INVALIDO"

    def __init__(self, mensagem: str, *, detalhes: dict[str, Any] | None = None) -> None:
        self.detalhes = detalhes or {}
        super().__init__(mensagem)


class TimeCheio(ErroDeTime):
    """Invariante 1: o time pedido tem mais Pokemon do que cabe."""

    codigo: ClassVar[str] = "TIME_CHEIO"


class TamanhoDeTimeInvalido(ErroDeTime):
    """Tamanho de time negativo: nao e jogada possivel, e sim chamada errada."""

    codigo: ClassVar[str] = "TAMANHO_DE_TIME_INVALIDO"


class PokemonDuplicado(ErroDeTime):
    """O mesmo Pokemon aparece duas vezes na lista (criterio 11 da spec 004)."""

    codigo: ClassVar[str] = "POKEMON_DUPLICADO"


class PokemonJaAtribuido(ErroDeTime):
    """Invariantes 2 e 4: o Pokemon ja esta no time de outro treinador."""

    codigo: ClassVar[str] = "POKEMON_JA_ATRIBUIDO"


class PokemonComprometido(ErroDeTime):
    """Invariante 14: o Pokemon esta reservado para uma entrega."""

    codigo: ClassVar[str] = "POKEMON_COMPROMETIDO"


class PokemonDesconhecido(ErroDeTime):
    """O Pokemon nao existe ou nao e deste laboratorio (regra 11 da spec 004)."""

    codigo: ClassVar[str] = "POKEMON_DESCONHECIDO"


class TreinadorOcupado(ErroDeTime):
    """Invariante 3: treinador em expedicao ou em entrega nao muda de time."""

    codigo: ClassVar[str] = "TREINADOR_OCUPADO"


# --- Entrada ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TreinadorAlvo:
    """O treinador cujo time esta sendo montado, como o dominio precisa ve-lo."""

    id: UUID
    status: StatusTreinador


@dataclass(frozen=True, slots=True)
class PokemonParaTime:
    """Estado de um Pokemon do laboratorio, do ponto de vista da montagem.

    Dataclass enxuta em vez do modelo ORM, como em `stats.py` e
    `kit_inicial.py`: o Artigo I nao sobreviveria a uma `PokemonInstancia` do
    SQLAlchemy atravessando esta fronteira.
    """

    id: UUID
    treinador_id: UUID | None = None
    comprometido_com_entrega: bool = False


# --- Saida -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TimeValidado:
    """O time aprovado e o que o servico precisa gravar para chegar nele."""

    treinador_id: UUID
    pokemon_ids: tuple[UUID, ...]
    para_adicionar: tuple[UUID, ...]
    para_remover: tuple[UUID, ...]

    @property
    def tamanho(self) -> int:
        return len(self.pokemon_ids)

    @property
    def capacidade_bagagem(self) -> int:
        return capacidade_bagagem(self.tamanho)


@dataclass(frozen=True, slots=True)
class PreviaDoTime:
    """Resultado da previa: a mesma validacao, sem levantar excecao.

    Quando `valido` e falso, `time` vem nulo de proposito — uma composicao
    recusada nao muda nada, entao a capacidade de bagagem que a tela deve
    continuar mostrando e a do time atual, nao a da composicao impossivel.
    """

    valido: bool
    time: TimeValidado | None = None
    codigo: str | None = None
    motivo: str | None = None


# --- Capacidade (invariante 11) ---------------------------------------------


def capacidade_bagagem_tolerante(tamanho_do_time: int) -> int:
    """Capacidade para EXIBIR, que nunca levanta.

    A leitura de um treinador nao pode explodir por causa de um time maior que
    o maximo: se isso aconteceu, e dado corrompido, e derrubar a listagem com
    500 esconde o problema em vez de mostra-lo. A escrita continua recusando
    pela `capacidade_bagagem`, que valida.
    """
    return max(0, balance.CAPACIDADE_TOTAL_TREINADOR - max(0, tamanho_do_time))


def validar_pedido(pokemon_ids: Sequence[UUID]) -> None:
    """Checagens que nao dependem do estado do banco.

    Separadas para que o servico recuse uma lista absurda ANTES de travar linha
    nenhuma: repeticao e tamanho sao verificaveis so com o que o cliente
    mandou. `validar_time` roda as mesmas de novo, e isso e de proposito — ela
    continua correta sozinha, para quem a chamar direto.
    """
    _exigir_lista_sem_repeticao(pokemon_ids)
    _exigir_tamanho_do_time(len(pokemon_ids))


def capacidade_bagagem(tamanho_do_time: int) -> int:
    """Quantos Pokemon o treinador ainda consegue trazer de uma expedicao.

    CAPACIDADE_TOTAL_TREINADOR menos o time: time grande vence mais encontros e
    captura menos, time pequeno faz o contrario (SDD 4.6). Time vazio da a
    capacidade maxima; time cheio da o que sobra dela.
    """
    if tamanho_do_time < 0:
        raise TamanhoDeTimeInvalido(f"Tamanho de time negativo: {tamanho_do_time}.")
    if tamanho_do_time > balance.TAMANHO_MAXIMO_TIME:
        raise TimeCheio(
            f"Um treinador leva no maximo {balance.TAMANHO_MAXIMO_TIME} Pokemon no time; "
            f"foram informados {tamanho_do_time}."
        )
    return balance.CAPACIDADE_TOTAL_TREINADOR - tamanho_do_time


# --- Validacao --------------------------------------------------------------


def time_atual(
    treinador_id: UUID, pokemon_conhecidos: Iterable[PokemonParaTime]
) -> tuple[UUID, ...]:
    """Quem esta hoje no time do treinador, na ordem em que o estado chegou."""
    return tuple(
        pokemon.id for pokemon in pokemon_conhecidos if pokemon.treinador_id == treinador_id
    )


def _exigir_treinador_livre(treinador: TreinadorAlvo) -> None:
    """Invariantes 3 e 4, checados antes de tudo.

    Vem primeiro porque e o motivo que o professor precisa ler: com o treinador
    em expedicao, nenhuma composicao serve, e reclamar do tamanho da lista
    esconderia a razao verdadeira. Vale inclusive para uma lista identica ao
    time atual — a Fase 6 despacha uma expedicao com o time que leu no envio, e
    uma reescrita "inofensiva" no meio do caminho e reescrita do mesmo jeito.
    """
    if treinador.status.ocupado:
        raise TreinadorOcupado(
            f"O treinador esta {DESCRICAO_DO_STATUS[treinador.status]} e so volta a ter "
            "o time alterado quando estiver de volta ao laboratorio.",
            detalhes={"status": treinador.status.value},
        )


def _exigir_lista_sem_repeticao(pokemon_ids: Sequence[UUID]) -> None:
    vistos: set[UUID] = set()
    for pokemon_id in pokemon_ids:
        if pokemon_id in vistos:
            raise PokemonDuplicado(
                "O mesmo Pokemon foi listado duas vezes no time.",
                detalhes={"pokemon_id": str(pokemon_id)},
            )
        vistos.add(pokemon_id)


def _exigir_pokemon_disponivel(
    pokemon_id: UUID, estado: PokemonParaTime | None, dono: UUID
) -> None:
    if estado is None:
        raise PokemonDesconhecido(
            "Este Pokemon nao esta no laboratorio.",
            detalhes={"pokemon_id": str(pokemon_id)},
        )
    if estado.comprometido_com_entrega:
        raise PokemonComprometido(
            "Este Pokemon esta reservado para uma entrega e nao pode entrar em time.",
            detalhes={"pokemon_id": str(pokemon_id)},
        )
    if estado.treinador_id is not None and estado.treinador_id != dono:
        raise PokemonJaAtribuido(
            "Este Pokemon ja esta no time de outro treinador.",
            detalhes={
                "pokemon_id": str(pokemon_id),
                "treinador_id": str(estado.treinador_id),
            },
        )


def _exigir_tamanho_do_time(quantidade: int) -> None:
    if quantidade > balance.TAMANHO_MAXIMO_TIME:
        raise TimeCheio(
            f"Um treinador leva no maximo {balance.TAMANHO_MAXIMO_TIME} Pokemon no time; "
            f"foram escolhidos {quantidade}. Os outros "
            f"{balance.CAPACIDADE_TOTAL_TREINADOR - balance.TAMANHO_MAXIMO_TIME} lugares da "
            f"mochila ficam reservados para o que ele capturar em campo.",
            detalhes={
                "maximo": balance.TAMANHO_MAXIMO_TIME,
                "escolhidos": quantidade,
                "capacidade_total": balance.CAPACIDADE_TOTAL_TREINADOR,
            },
        )


def validar_time(
    treinador: TreinadorAlvo,
    pokemon_ids: Sequence[UUID],
    pokemon_conhecidos: Iterable[PokemonParaTime],
) -> TimeValidado:
    """Aprova a composicao pretendida ou recusa com o motivo especifico.

    A ordem das checagens e a ordem do que interessa ao professor: primeiro o
    treinador, depois a lista como um todo, depois cada Pokemon na ordem em que
    ele os escolheu.
    """
    _exigir_treinador_livre(treinador)
    _exigir_lista_sem_repeticao(pokemon_ids)
    _exigir_tamanho_do_time(len(pokemon_ids))

    conhecidos = {pokemon.id: pokemon for pokemon in pokemon_conhecidos}
    for pokemon_id in pokemon_ids:
        _exigir_pokemon_disponivel(pokemon_id, conhecidos.get(pokemon_id), treinador.id)

    pedidos = tuple(pokemon_ids)
    atuais = time_atual(treinador.id, conhecidos.values())
    return TimeValidado(
        treinador_id=treinador.id,
        pokemon_ids=pedidos,
        para_adicionar=tuple(um for um in pedidos if um not in atuais),
        para_remover=tuple(um for um in atuais if um not in pedidos),
    )


def prever_time(
    treinador: TreinadorAlvo,
    pokemon_ids: Sequence[UUID],
    pokemon_conhecidos: Iterable[PokemonParaTime],
) -> PreviaDoTime:
    """A mesma validacao do salvamento, com o erro devolvido em vez de levantado.

    E a funcao da previa de montagem: a tela precisa do motivo para exibir,
    nao de uma excecao para tratar.
    """
    try:
        time = validar_time(treinador, pokemon_ids, pokemon_conhecidos)
    except ErroDeTime as erro:
        return PreviaDoTime(valido=False, codigo=erro.codigo, motivo=str(erro))
    return PreviaDoTime(valido=True, time=time)
