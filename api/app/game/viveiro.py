"""O viveiro do laboratorio: ocupacao, transbordo e a guarda do despacho.

Implementa a secao 4.10 do SDD e os invariantes 20 e 21. Tres decisoes de
desenho valem o comentario, e as tres sao a mesma regra vista de angulos
diferentes.

**A ocupacao e derivada, nunca gravada.** Nao ha contador de viveiro em lugar
nenhum: a ocupacao e a contagem dos Pokemon do laboratorio com `treinador_id`
nulo, feita na hora. Um contador materializado divergiria no primeiro caminho
que esquecesse de atualiza-lo — e os caminhos que criam e destroem Pokemon ja
sao cinco (kit inicial, captura, soltura, aceite e conclusao de entrega) —, e
um contador errado aqui aparece como professor travado sem motivo visivel. A
contagem e barata com indice em `laboratorio_id, treinador_id`.

**O viveiro transborda, e isso e o desenho.** O limite NAO morde na captura:
`game/expedition.resolver` nao conhece este modulo e nao vai conhecer. Tres
expedicoes podem voltar com quinze Pokemon para dois lugares, e os quinze
entram. Travar no despacho por espaco livre protegeria o professor da decisao
que e o ponto do sistema — a escassez so e sentida quando ele precisa olhar
para catorze Rattata e escolher quem fica. Isso tambem preserva o invariante
19 inteiro: o resultado da expedicao continua funcao apenas da semente e do
estado gravado no envio.

**Transbordado, o viveiro trava UMA COISA SO: o despacho de expedicao nova.**
Reclamar relatorio, aceitar entrega, concluir entrega e soltar continuam
liberados — sao as saidas, e fechar a saida de quem esta preso e o pior
defeito possivel aqui. O sintoma seria um jogador travado sem entender por
que, e nao um erro no log. Por isso `exigir_espaco_para_despachar` existe uma
vez e e chamada de um lugar so.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, ClassVar
from uuid import UUID

from app.game import balance
from app.game.erros import ErroDeDominio

# --- Erros (Artigo VI) ------------------------------------------------------


class ErroDeViveiro(ErroDeDominio):
    """Raiz das recusas do viveiro.

    O `codigo` e o mesmo do contrato de API, declarado uma vez aqui para que o
    router nao tenha a propria tabela de traducao, como em `team.py`,
    `mapa.py` e `expedition.py`.
    """

    codigo: ClassVar[str] = "VIVEIRO_INVALIDO"

    def __init__(self, mensagem: str, *, detalhes: dict[str, Any] | None = None) -> None:
        self.detalhes = detalhes or {}
        super().__init__(mensagem)


class OcupacaoInvalida(ErroDeViveiro):
    """Ocupacao negativa: nao e jogada possivel, e sim chamada errada.

    Contagem nao e negativa. Chegar aqui significa que quem chamou subtraiu
    antes de passar o numero, e e melhor levantar do que devolver um viveiro
    com lugares a mais.
    """

    codigo: ClassVar[str] = "OCUPACAO_INVALIDA"


class ViveiroTransbordado(ErroDeViveiro):
    """Invariante 21: com o viveiro acima da capacidade, nenhuma expedicao parte.

    Carrega `lugares_faltando` nos detalhes porque a recusa precisa dizer
    quanto falta: "o viveiro esta cheio" nao informa se o professor solta um
    Pokemon ou doze.
    """

    codigo: ClassVar[str] = "VIVEIRO_TRANSBORDADO"


# --- Entrada ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PokemonDoLaboratorio:
    """Um Pokemon do acervo, do ponto de vista do viveiro e da soltura.

    Dataclass enxuta em vez do modelo ORM, pelo mesmo motivo de
    `team.PokemonParaTime`: o Artigo I nao sobreviveria a uma
    `PokemonInstancia` do SQLAlchemy atravessando esta fronteira.

    `comprometido_entrega_id` guarda o id da entrega, e nao um booleano, para
    que a recusa de soltura possa dizer **qual** entrega prende o Pokemon — a
    tela precisa disso para oferecer o caminho de volta.
    """

    id: UUID
    treinador_id: UUID | None = None
    comprometido_entrega_id: UUID | None = None

    @property
    def no_viveiro(self) -> bool:
        """Se este Pokemon ocupa lugar (invariante 20).

        Quem esta num time viaja com o treinador e nao conta. Quem esta
        comprometido com uma entrega CONTA: ele continua no laboratorio ate a
        entrega ser concluida, e e so ali que o lugar volta.
        """
        return self.treinador_id is None


# --- Saida ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EstadoDoViveiro:
    """O que o professor ve ao abrir o viveiro (criterio 1 da spec 008).

    Os quatro campos saem da mesma contagem e sao devolvidos juntos para que
    tela e servico nunca refacam a conta por conta propria — repetir
    `ocupacao > capacidade` em dois lugares e como eles passam a discordar.
    """

    capacidade: int
    ocupacao: int
    transbordado: bool
    lugares_faltando: int


# --- Contagem ---------------------------------------------------------------


def _exigir_ocupacao_valida(ocupacao: int) -> None:
    if ocupacao < 0:
        raise OcupacaoInvalida(f"A ocupacao do viveiro nao pode ser negativa: {ocupacao}.")


def ocupacao(pokemon_do_laboratorio: Iterable[PokemonDoLaboratorio]) -> int:
    """Quantos lugares estao ocupados agora (invariante 20).

    Conta quem tem `treinador_id` nulo. Quem esta num time nao conta, porque
    viaja com o treinador; quem esta comprometido com uma entrega conta,
    porque ainda esta no laboratorio.

    O servico pode chegar ao mesmo numero com um `count(*)` e passa-lo direto
    para `transbordado` e `lugares_faltando` — esta funcao existe para quem ja
    tem a lista carregada, como o `GET /ranch`, que precisa dos itens de todo
    jeito.
    """
    return sum(1 for pokemon in pokemon_do_laboratorio if pokemon.no_viveiro)


def transbordado(ocupacao: int) -> bool:
    """Se o viveiro passou da capacidade (invariante 20).

    Estritamente **acima** da capacidade. Com exatamente `CAPACIDADE_VIVEIRO`
    ocupados o viveiro esta cheio, nao transbordado: os cinquenta cabem, e
    quem cabe nao bloqueia nada.
    """
    _exigir_ocupacao_valida(ocupacao)
    return ocupacao > balance.CAPACIDADE_VIVEIRO


def lugares_faltando(ocupacao: int) -> int:
    """Quantos Pokemon precisam sair para o viveiro voltar a caber.

    Zero quando nao ha transbordo — inclusive com o viveiro exatamente cheio.
    Nunca negativo: lugar vago nao e lugar faltando, e devolver a sobra aqui
    faria a tela anunciar "faltam -7 lugares".
    """
    _exigir_ocupacao_valida(ocupacao)
    return max(0, ocupacao - balance.CAPACIDADE_VIVEIRO)


def estado_do_viveiro(ocupacao_atual: int) -> EstadoDoViveiro:
    """Os quatro numeros do `GET /ranch`, derivados de uma contagem so."""
    return EstadoDoViveiro(
        capacidade=balance.CAPACIDADE_VIVEIRO,
        ocupacao=ocupacao_atual,
        transbordado=transbordado(ocupacao_atual),
        lugares_faltando=lugares_faltando(ocupacao_atual),
    )


# --- A guarda do despacho, e so ela -----------------------------------------


def exigir_espaco_para_despachar(ocupacao_atual: int) -> None:
    """Invariante 21: viveiro transbordado nao deixa expedicao nova partir.

    **Esta funcao e chamada de um lugar so**: o servico de despacho de
    expedicao. Ela nao aparece em reclamar relatorio, em aceitar entrega, em
    concluir entrega nem em soltar — esses quatro sao as saidas, e sao
    justamente o que o professor precisa usar para sair do transbordo.
    Acrescentar aqui uma chamada a mais, com a boa intencao de "proteger"
    outro caminho, prende o professor sem saida; e o risco nomeado no plano da
    spec 008 e o motivo de a regra 4 existir.

    A recusa leva `lugares_faltando` nos detalhes: a tela precisa dizer
    quantos Pokemon soltar ou entregar, e nao so que o viveiro encheu.
    """
    if not transbordado(ocupacao_atual):
        return
    faltam = lugares_faltando(ocupacao_atual)
    raise ViveiroTransbordado(
        f"O viveiro esta com {ocupacao_atual} Pokemon para {balance.CAPACIDADE_VIVEIRO} lugares. "
        f"Solte ou entregue {faltam} para despachar uma expedicao nova.",
        detalhes={
            "capacidade": balance.CAPACIDADE_VIVEIRO,
            "ocupacao": ocupacao_atual,
            "lugares_faltando": faltam,
        },
    )
