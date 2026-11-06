"""Despacho de expedicao: dificuldade, chance, prazo e estado observado.

Este modulo fecha a secao 4.3 do SDD — a Fase 4 trouxe so o poder do time — e
responde as duas perguntas da Fase 6: **esta expedicao pode partir?** e, dado
que partiu, **em que estado ela esta agora?**

Quatro decisoes de desenho valem o comentario.

**O relogio chega como parametro.** Nada aqui le `datetime.now()`: o `agora` e
argumento de toda funcao que precisa dele, como manda o Artigo I. E o que
permite testar a virada do `eta` sem esperar nem congelar o relogio do
processo, e e tambem o que torna possivel a prova do determinismo — duas
chamadas com o mesmo `agora` dao o mesmo `eta`, sempre.

**O estado e derivado, nao gravado.** Uma expedicao cujo `eta` ja passou nao
esta mais em curso, mas nenhuma linha do banco mudou: ela esta
`AGUARDANDO_RELATORIO`, terminada e a espera da resolucao da Fase 7. Gravar
essa transicao exigiria um job varrendo o banco, e o ADR-004 decidiu nao ter
um. A consequencia e que **toda leitura precisa derivar**, e por isso a
derivacao mora numa funcao so: dois lugares derivando diferente seria um bug
que aparece como contador travado em zero numa tela e expedicao resolvida na
outra.

**A previa e o despacho chamam a mesma funcao.** `prever_despacho` e
`calcular_despacho` com o erro devolvido em vez de levantado, mesmo arranjo
que `team.prever_time`. Previa e envio que validam por caminhos diferentes
divergem no primeiro invariante novo, e o professor leva um erro no botao que
a previa jurava que nao existia.

**A dificuldade e a chance saem arredondadas, e e de proposito.** Elas sao
gravadas em `dificuldade_calculada` e exibidas ao professor; a Fase 7 vai
resolver os encontros a partir das mesmas colunas e precisa chegar no mesmo
numero. Um relatorio que explica a derrota com uma chance diferente da que foi
mostrada no envio nao explica nada.

A escala de tempo (`EXPEDITION_TIME_SCALE`, ADR-004) **multiplica** e e
ambiente, nao calibragem: nao esta em `balance.py` e nao e lida aqui dentro —
chega como argumento e segue para `mapa.duracao_estimada`.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from fractions import Fraction
from math import exp
from typing import Any, ClassVar
from uuid import UUID

from app.game import balance
from app.game.erros import ErroDeDominio
from app.game.mapa import (
    DestinoForaDeAlcance,
    GrafoDeLocais,
    RotaAteLocal,
    duracao_da_rota,
    exigir_destino_alcancavel,
)
from app.game.power import PokemonNoTime, poder_do_time
from app.game.team import ErroDeTime, capacidade_bagagem
from app.game.trainers import DESCRICAO_DO_STATUS, StatusTreinador

# --- Erros (Artigo VI) ------------------------------------------------------


class ErroDeExpedicao(ErroDeDominio):
    """Raiz das recusas de despacho.

    O `codigo` e o mesmo do contrato de API, declarado uma vez aqui para que o
    router nao tenha a propria tabela de traducao, como ja se faz em `team.py`
    e em `mapa.py`.
    """

    codigo: ClassVar[str] = "EXPEDICAO_INVALIDA"

    def __init__(self, mensagem: str, *, detalhes: dict[str, Any] | None = None) -> None:
        self.detalhes = detalhes or {}
        super().__init__(mensagem)


class TimeVazio(ErroDeExpedicao):
    """Invariante 17: expedicao exige treinador com ao menos um Pokemon."""

    codigo: ClassVar[str] = "TIME_VAZIO"


class TreinadorIndisponivel(ErroDeExpedicao):
    """Invariante 3: treinador em expedicao ou em entrega nao recebe missao.

    Nome diferente de `team.TreinadorOcupado` de proposito, apesar do mesmo
    codigo de contrato: os dois erros convivem no mesmo servico, e dois nomes
    iguais importados de modulos diferentes viram alias e depois viram bug.
    """

    codigo: ClassVar[str] = "TREINADOR_OCUPADO"


class EstoqueInsuficiente(ErroDeExpedicao):
    """Invariante 9: nao se leva mais item do que ha em estoque."""

    codigo: ClassVar[str] = "ESTOQUE_INSUFICIENTE"


class CargaInvalida(ErroDeExpedicao):
    """A carga pedida nao descreve uma mochila possivel."""

    codigo: ClassVar[str] = "CARGA_INVALIDA"


class SementeInvalida(ErroDeExpedicao):
    """A semente nao cabe no que a expedicao grava (ADR-005)."""

    codigo: ClassVar[str] = "SEMENTE_INVALIDA"


class LocalInvalido(ErroDeExpedicao):
    """Os numeros do local nao descrevem um destino possivel."""

    codigo: ClassVar[str] = "LOCAL_INVALIDO"


class PoderInvalido(ErroDeExpedicao):
    """Poder ou dificuldade negativos: nao e jogada possivel, e chamada errada."""

    codigo: ClassVar[str] = "PODER_INVALIDO"


class RelogioSemFuso(ErroDeExpedicao):
    """Um instante chegou sem fuso horario.

    Comparar um `datetime` ingenuo com um com fuso levanta `TypeError` em
    Python, e esse e o tipo de bug que so aparece em producao, na primeira
    leitura de uma expedicao gravada. Recusar na entrada transforma isso num
    erro de dominio com mensagem, no lugar onde o dado entrou.
    """

    codigo: ClassVar[str] = "RELOGIO_SEM_FUSO"


# --- Entrada ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TreinadorParaExpedicao:
    """O treinador que vai ser despachado, como o dominio precisa ve-lo."""

    id: UUID
    nivel: int
    status: StatusTreinador


@dataclass(frozen=True, slots=True)
class LocalDaExpedicao:
    """O destino, do ponto de vista da dificuldade (SDD 4.3).

    Nao repete `custo_travessia_minutos` nem `encontros_base`: esses ja vem do
    `LocalNoGrafo` de `mapa.py`, e dois lugares guardando o mesmo numero
    divergem na primeira mudanca de seed. Aqui ficam so os campos que a
    dificuldade usa e que o grafo nao carrega.

    A validacao acontece na construcao porque um local com faixa de nivel
    invertida nao e jogada possivel: e seed errado, e errar cedo mostra o
    problema em vez de produzir uma dificuldade plausivel e errada.
    """

    id: str
    nivel_selvagem_min: int
    nivel_selvagem_max: int
    nivel_dificuldade: int

    def __post_init__(self) -> None:
        if self.nivel_selvagem_min < 1:
            raise LocalInvalido(
                f"O local {self.id!r} tem nivel selvagem minimo invalido: "
                f"{self.nivel_selvagem_min}.",
                detalhes={"local_id": self.id},
            )
        if self.nivel_selvagem_max > balance.NIVEL_MAXIMO:
            raise LocalInvalido(
                f"O local {self.id!r} tem nivel selvagem acima de {balance.NIVEL_MAXIMO}: "
                f"{self.nivel_selvagem_max}.",
                detalhes={"local_id": self.id},
            )
        if self.nivel_selvagem_min > self.nivel_selvagem_max:
            raise LocalInvalido(
                f"O local {self.id!r} tem a faixa de nivel selvagem invertida: "
                f"{self.nivel_selvagem_min} a {self.nivel_selvagem_max}.",
                detalhes={"local_id": self.id},
            )
        if self.nivel_dificuldade < 0:
            raise LocalInvalido(
                f"O local {self.id!r} tem nivel de dificuldade negativo: {self.nivel_dificuldade}.",
                detalhes={"local_id": self.id},
            )

    @property
    def nivel_selvagem_medio(self) -> Fraction:
        """A media exata da faixa, que e o que a dificuldade multiplica.

        Racional e nao float: a faixa de 7 a 12 do Mt. Moon tem media 9,5, e
        arredondar para 9 ou 10 antes da multiplicacao moveria a dificuldade
        do lugar inteiro em meio ponto.
        """
        return Fraction(self.nivel_selvagem_min + self.nivel_selvagem_max, 2)


@dataclass(frozen=True, slots=True)
class ItemNaCarga:
    """Um item da mochila, com o que ha em estoque no momento do envio.

    O estoque viaja junto do pedido, e nao num dicionario a parte, porque e
    exatamente o par que o invariante 9 compara — separa-los permitiria chamar
    a validacao com metade da informacao.

    `efeito_duracao` vem do seed do item (SDD 3.1) e e o que acelera a
    expedicao; para Pokebola ele e zero.
    """

    item_id: str
    quantidade: int
    quantidade_em_estoque: int
    efeito_duracao: float = 0.0


# --- Saida -----------------------------------------------------------------


class StatusExpedicao(StrEnum):
    """O que a coluna `status` grava (SDD 3.2).

    `AGUARDANDO_RELATORIO` nao esta aqui de proposito: ele nao e fato gravado,
    e sim leitura do relogio contra o `eta`.
    """

    EM_CURSO = "EM_CURSO"
    CONCLUIDA_SUCESSO = "CONCLUIDA_SUCESSO"
    CONCLUIDA_FALHA = "CONCLUIDA_FALHA"
    ABORTADA = "ABORTADA"

    @property
    def terminal(self) -> bool:
        """Status do qual a expedicao nao sai mais: o `eta` deixou de importar."""
        return self is not StatusExpedicao.EM_CURSO


class EstadoObservado(StrEnum):
    """O estado que o professor ve, que e o gravado mais o relogio.

    Tem um valor a mais que `StatusExpedicao`, e so um: `AGUARDANDO_RELATORIO`,
    a expedicao que acabou e ainda nao foi resolvida.
    """

    EM_CURSO = "EM_CURSO"
    AGUARDANDO_RELATORIO = "AGUARDANDO_RELATORIO"
    CONCLUIDA_SUCESSO = "CONCLUIDA_SUCESSO"
    CONCLUIDA_FALHA = "CONCLUIDA_FALHA"
    ABORTADA = "ABORTADA"

    @property
    def precisa_de_resolucao(self) -> bool:
        """Se a Fase 7 ainda deve resolver esta expedicao ao le-la."""
        return self is EstadoObservado.AGUARDANDO_RELATORIO

    @property
    def terminal(self) -> bool:
        """Se a expedicao acabou de verdade, com resultado ja gravado."""
        return self in (
            EstadoObservado.CONCLUIDA_SUCESSO,
            EstadoObservado.CONCLUIDA_FALHA,
            EstadoObservado.ABORTADA,
        )


@dataclass(frozen=True, slots=True)
class DespachoCalculado:
    """Tudo o que o servico precisa gravar para a expedicao partir.

    Traz a rota inteira, e nao so o destino, porque a origem e o caminho sao
    colunas da expedicao e recalcula-los depois significaria rodar Dijkstra de
    novo — com os visitados ja mudados pela propria expedicao, o que daria
    outra resposta.
    """

    treinador_id: UUID
    destino_id: str
    origem_id: str
    caminho: tuple[str, ...]
    custo_viagem_minutos: int
    duracao_minutos: int
    started_at: datetime
    eta: datetime
    seed: int
    poder_time: float
    dificuldade: float
    chance_estimada: float
    capacidade_bagagem: int
    bonus_itens: float
    carga: tuple[ItemNaCarga, ...] = ()

    @property
    def debitos(self) -> tuple[tuple[str, int], ...]:
        """O que sai do estoque no envio (regra 3 da spec 006), ordenado por item.

        Ordenado porque o servico trava as linhas de estoque nessa ordem para
        nao abracar deadlock com um despacho concorrente.
        """
        return tuple(sorted((item.item_id, item.quantidade) for item in self.carga))


@dataclass(frozen=True, slots=True)
class PreviaDoDespacho:
    """Resultado da previa: a mesma validacao, sem levantar excecao.

    Quando `valido` e falso, `despacho` vem nulo — uma expedicao recusada nao
    tem duracao nem `eta`, e inventar os dois para preencher a tela seria
    prometer um prazo que nao existe.
    """

    valido: bool
    despacho: DespachoCalculado | None = None
    codigo: str | None = None
    motivo: str | None = None
    detalhes: dict[str, Any] = field(default_factory=dict)


# --- Dificuldade e chance (SDD 4.3) -----------------------------------------


def _fracao(valor: float) -> Fraction:
    """`Fraction(str(0.03))` da 3/100; `Fraction(0.03)` daria a aproximacao binaria.

    Mesma decisao de `power.py` e `mapa.py`: a conta corre exata para que a
    calibragem da Fase 9 nao mude um arredondamento por efeito colateral.
    """
    return Fraction(str(valor))


def _arredondar(valor: Fraction | float, casas: int) -> float:
    escala = 10**casas
    return round(valor * escala) / escala


def dificuldade_do_local(local: LocalDaExpedicao) -> float:
    """`nivel_selvagem_medio * nivel_dificuldade * FATOR_DIFICULDADE` (SDD 4.3).

    Conferencia contra o seed da v1: Pallet Town, faixa 2 a 4 e dificuldade 1,
    da 3,0; Mt. Moon, faixa 7 a 12 e dificuldade 5, da 47,5; Cerulean City,
    faixa 10 a 14 e dificuldade 6, da 72,0.

    Um local de dificuldade zero e degenerado — nao ha seed assim — mas a
    funcao devolve zero em vez de recusar: quem divide por ela e
    `chance_estimada`, e e la que a decisao de nao dividir por zero mora.
    """
    fator = _fracao(balance.FATOR_DIFICULDADE)
    bruta = local.nivel_selvagem_medio * local.nivel_dificuldade * fator
    return _arredondar(bruta, balance.CASAS_DECIMAIS_DIFICULDADE)


def chance_estimada(poder_time: float, dificuldade: float) -> float:
    """A sigmoide da secao 4.3, achatada entre 5% e 95%.

        razao     = poder_time / dificuldade
        p_vitoria = clamp(1 / (1 + e^(-INCLINACAO_SIGMOIDE * (razao - 1))),
                          P_VITORIA_MINIMA, P_VITORIA_MAXIMA)

    Os dois limites sao inviolaveis e existem para que o jogo nunca fique sem
    historia: uma expedicao suicida ainda pode dar certo, e uma trivial ainda
    pode falhar. Nenhuma razao, por mais extrema, passa deles.

    **Dificuldade zero nao divide por zero**: ela devolve o teto. Um lugar sem
    nenhum perigo e vencido por qualquer time, inclusive por um time vazio — e
    "qualquer time vence" e exatamente o que `P_VITORIA_MAXIMA` significa.
    Recusar com erro seria a outra saida possivel, e foi descartada porque a
    previa precisa responder alguma coisa sobre todo destino do mapa, e um
    local degenerado no seed derrubaria a tela em vez de aparecer como trivial.

    A Fase 7 chama esta mesma funcao para resolver cada encontro de verdade.
    Aqui ela serve a previa; sao o mesmo numero de proposito.
    """
    if poder_time < 0:
        raise PoderInvalido(f"O poder do time nao pode ser negativo: {poder_time}.")
    if dificuldade < 0:
        raise PoderInvalido(f"A dificuldade nao pode ser negativa: {dificuldade}.")
    if dificuldade == 0:
        return _limitar(Fraction(1))

    razao = _fracao(poder_time) / _fracao(dificuldade)
    expoente = -_fracao(balance.INCLINACAO_SIGMOIDE) * (razao - 1)
    if expoente < -_fracao(balance.EXPOENTE_LIMITE_SIGMOIDE):
        # Abaixo deste expoente o exp() duplo ja e zero e a conversao do
        # racional para float estouraria: a sigmoide esta colada no teto.
        return _limitar(Fraction(1))
    return _limitar(1 / (1 + exp(float(expoente))))


def _limitar(chance: Fraction | float) -> float:
    """Aplica o clamp antes do arredondamento, nunca depois.

    Arredondar primeiro poderia empurrar uma chance de 0,04999 para dentro da
    faixa por acidente, e o limite deixaria de ser limite.
    """
    limitada = min(max(float(chance), balance.P_VITORIA_MINIMA), balance.P_VITORIA_MAXIMA)
    return _arredondar(limitada, balance.CASAS_DECIMAIS_CHANCE)


# --- Relogio ----------------------------------------------------------------


def exigir_instante_com_fuso(instante: datetime, *, nome: str) -> datetime:
    """Recusa `datetime` ingenuo, que e o unico jeito de a comparacao estourar.

    Todo instante do PokeLab e UTC com fuso. Um valor sem fuso compara com
    `TypeError` contra qualquer outro que tenha, e a conversao silenciosa para
    UTC seria pior: ela acerta em maquina configurada em UTC e erra em todas as
    outras, que e como um bug de fuso sobrevive ao desenvolvimento inteiro.
    """
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise RelogioSemFuso(
            f"O instante {nome} chegou sem fuso horario: {instante.isoformat()}.",
            detalhes={"parametro": nome},
        )
    return instante


def status_de_expedicao(valor: str | StatusExpedicao) -> StatusExpedicao:
    """Converte o texto gravado na coluna em status, recusando o que nao reconhece."""
    try:
        return StatusExpedicao(valor)
    except ValueError:
        nomes = ", ".join(status.value for status in StatusExpedicao)
        raise ErroDeExpedicao(
            f"Status de expedicao desconhecido: {valor!r}. Esperado um de: {nomes}."
        ) from None


def estado_observado(
    status_gravado: str | StatusExpedicao,
    eta: datetime,
    agora: datetime,
) -> EstadoObservado:
    """O estado real da expedicao: o que esta gravado, corrigido pelo relogio.

    Esta e a **unica** funcao que deriva estado de expedicao. Toda leitura
    passa por aqui — lista, detalhe e a resolucao da Fase 7 —, porque dois
    lugares comparando o `eta` por conta propria acabariam discordando no
    limite, e o limite e justo onde o professor esta olhando.

    Status terminal ignora o `eta`: uma expedicao abortada nao volta a estar em
    curso nem passa a aguardar relatorio por causa de um prazo que expirou
    depois do aborto.

    No empate — `agora` exatamente igual ao `eta` — a expedicao **ja terminou**.
    O `eta` e o instante do retorno, nao o ultimo instante da viagem, e a
    alternativa deixaria a tela mostrando "0 segundos restantes" ao lado de
    "em curso", que e uma contradicao que o professor enxerga.
    """
    status = status_de_expedicao(status_gravado)
    exigir_instante_com_fuso(eta, nome="eta")
    exigir_instante_com_fuso(agora, nome="agora")
    if status.terminal:
        return EstadoObservado(status.value)
    if agora >= eta:
        return EstadoObservado.AGUARDANDO_RELATORIO
    return EstadoObservado.EM_CURSO


def tempo_restante(eta: datetime, agora: datetime) -> int:
    """Quantos segundos faltam, nunca negativo (regra 10 da spec 006).

    Arredonda para cima: enquanto sobrar qualquer fracao de segundo, falta um
    segundo. E o que mantem a coerencia com `estado_observado` — zero segundos
    restantes acontece exatamente quando o estado e `AGUARDANDO_RELATORIO`, e
    nunca antes. Arredondar para baixo mostraria "0s" numa expedicao que a
    mesma resposta declara em curso.

    A conta corre em `timedelta` inteiro, sem passar por `total_seconds()`:
    ponto flutuante aqui transformaria 1 microssegundo restante em zero.
    """
    exigir_instante_com_fuso(eta, nome="eta")
    exigir_instante_com_fuso(agora, nome="agora")
    falta = eta - agora
    if falta <= timedelta(0):
        return 0
    segundo = timedelta(seconds=1)
    inteiros, resto = divmod(falta, segundo)
    return inteiros + (1 if resto else 0)


# --- Despacho ---------------------------------------------------------------


def _exigir_treinador_disponivel(treinador: TreinadorParaExpedicao) -> None:
    """Invariante 3 do SDD 3.3.

    Vem antes de tudo pelo mesmo motivo de `team._exigir_treinador_livre`: com
    o treinador em expedicao nenhuma escolha de destino ou de carga serve, e
    reclamar da mochila esconderia a razao verdadeira.
    """
    if treinador.status.ocupado:
        raise TreinadorIndisponivel(
            f"O treinador esta {DESCRICAO_DO_STATUS[treinador.status]} e so recebe uma nova "
            "missao quando voltar ao laboratorio.",
            detalhes={"treinador_id": str(treinador.id), "status": treinador.status.value},
        )


def _exigir_time_nao_vazio(
    treinador: TreinadorParaExpedicao, time: Sequence[PokemonNoTime]
) -> None:
    """Invariante 17 do SDD 3.3.

    Um treinador sem Pokemon e estado valido — e como os tres comecam —, o que
    nao vale e despacha-lo: sem time nao ha o que vencer um encontro, e a
    expedicao voltaria em falha garantida depois de consumir tempo e itens.
    """
    if not time:
        raise TimeVazio(
            "Este treinador nao tem nenhum Pokemon no time e nao pode sair em expedicao. "
            "Monte o time dele antes de despachar.",
            detalhes={"treinador_id": str(treinador.id)},
        )


def _exigir_carga_possivel(carga: Sequence[ItemNaCarga]) -> None:
    """Invariante 9 do SDD 3.3, mais a sanidade do pedido.

    O item repetido e recusado em vez de somado: duas linhas de duas Pocoes
    contra um estoque de tres passariam uma a uma e estourariam o estoque
    juntas, e somar silenciosamente esconderia que o pedido chegou
    contraditorio — as duas linhas trazem o proprio `quantidade_em_estoque`, e
    nada garante que concordem.
    """
    vistos: set[str] = set()
    for item in carga:
        if item.item_id in vistos:
            raise CargaInvalida(
                f"O item {item.item_id!r} aparece duas vezes na carga.",
                detalhes={"item_id": item.item_id},
            )
        vistos.add(item.item_id)
        if item.quantidade < 1:
            raise CargaInvalida(
                f"A quantidade de {item.item_id!r} na carga precisa ser ao menos 1; "
                f"foi informada {item.quantidade}.",
                detalhes={"item_id": item.item_id, "quantidade": item.quantidade},
            )
        if item.quantidade_em_estoque < 0:
            raise CargaInvalida(
                f"O estoque de {item.item_id!r} chegou negativo: {item.quantidade_em_estoque}.",
                detalhes={"item_id": item.item_id},
            )
        if item.quantidade > item.quantidade_em_estoque:
            raise EstoqueInsuficiente(
                f"Nao ha {item.quantidade} de {item.item_id!r} no estoque: "
                f"restam {item.quantidade_em_estoque}.",
                detalhes={
                    "item_id": item.item_id,
                    "pedido": item.quantidade,
                    "disponivel": item.quantidade_em_estoque,
                },
            )


def _exigir_semente(seed: int) -> None:
    """ADR-005: a semente e gravada e sera reusada para reproduzir o relatorio."""
    if seed < 0 or seed > balance.SEED_MAXIMO:
        raise SementeInvalida(
            f"A semente da expedicao precisa estar entre 0 e {balance.SEED_MAXIMO}; "
            f"foi informada {seed}.",
            detalhes={"seed": seed},
        )


def bonus_de_itens(carga: Sequence[ItemNaCarga]) -> float:
    """Quanto a carga de suporte acelera a expedicao, limitado ao teto (SDD 4.4).

    O efeito e multiplicado pela quantidade: levar cinco Pocoes acelera mais
    que levar uma, que e o que "carga de suporte acelera" quer dizer. O teto de
    `BONUS_ITENS_MAXIMO` e o que impede a mochila gigante de zerar a duracao —
    com Pocao a 0,02, treze delas ja saturam.

    O corte acontece aqui e de novo em `mapa.duracao_estimada`, de proposito: a
    duracao precisa estar certa para quem a chama direto, e a previa precisa
    exibir o bonus que de fato foi aplicado.
    """
    bruto = sum(
        (_fracao(item.efeito_duracao) * item.quantidade for item in carga),
        Fraction(0),
    )
    if bruto < 0:
        raise CargaInvalida(f"A carga tem efeito de duracao negativo: {float(bruto)}.")
    return float(min(bruto, _fracao(balance.BONUS_ITENS_MAXIMO)))


def calcular_despacho(
    *,
    treinador: TreinadorParaExpedicao,
    time: Sequence[PokemonNoTime],
    grafo: GrafoDeLocais,
    visitados: Collection[str],
    destino: LocalDaExpedicao,
    seed: int,
    agora: datetime,
    carga: Sequence[ItemNaCarga] = (),
    escala: float = 1.0,
) -> DespachoCalculado:
    """Valida os invariantes do envio e devolve o que a expedicao vai gravar.

    Recebe o grafo e os visitados em vez da rota ja pronta: a rota sai de
    `mapa.exigir_destino_alcancavel`, que e quem impoe o invariante 6, e
    receber a rota de fora significaria confiar que alguem ja validou o alcance
    — exatamente o tipo de validacao que o Artigo VI manda nao terceirizar. O
    `destino` chega como `LocalDaExpedicao` porque o grafo nao carrega os
    numeros da dificuldade; os dois precisam falar do mesmo `id`, e um destino
    ausente do grafo levanta `LocalDesconhecido`, que o router traduz em 404.

    Cada invariante tem erro proprio, e nao um "pedido invalido" generico: a
    previa mostra o motivo enquanto o professor escolhe, e "o treinador esta em
    expedicao" e uma frase util, enquanto "despacho invalido" nao e.

    A ordem das checagens e a ordem do que interessa a quem le: primeiro o
    treinador, depois o destino, depois a mochila.

    `seed` chega de fora e nao e sorteado aqui (ADR-005 e Artigo I): quem tem
    direito a aleatoriedade nao determinista e o servico. O dominio so carrega
    a semente para dentro da expedicao.

    `escala` e o `EXPEDITION_TIME_SCALE` do ADR-004, que **multiplica**: 0,01
    encolhe a expedicao, e nao a alonga. Com o piso de
    `DURACAO_MINIMA_MINUTOS`, em desenvolvimento toda expedicao vira uma
    expedicao de um minuto.
    """
    exigir_instante_com_fuso(agora, nome="agora")
    _exigir_semente(seed)
    _exigir_treinador_disponivel(treinador)
    _exigir_time_nao_vazio(treinador, time)

    rota = exigir_destino_alcancavel(grafo, visitados, destino.id)

    _exigir_carga_possivel(carga)
    bonus = bonus_de_itens(carga)

    duracao_minutos = duracao_da_rota(
        grafo,
        rota,
        nivel_treinador=treinador.nivel,
        bonus_itens=bonus,
        escala=escala,
    )
    poder = poder_do_time(time, treinador.nivel)
    dificuldade = dificuldade_do_local(destino)

    return DespachoCalculado(
        treinador_id=treinador.id,
        destino_id=rota.destino_id,
        origem_id=rota.origem_id,
        caminho=rota.caminho,
        custo_viagem_minutos=rota.custo_viagem_minutos,
        duracao_minutos=duracao_minutos,
        started_at=agora,
        eta=_eta_de(agora, duracao_minutos),
        seed=seed,
        poder_time=poder,
        dificuldade=dificuldade,
        chance_estimada=chance_estimada(poder, dificuldade),
        capacidade_bagagem=capacidade_bagagem(len(time)),
        bonus_itens=bonus,
        carga=tuple(carga),
    )


def _eta_de(inicio: datetime, duracao_minutos: int) -> datetime:
    """O `eta` sai da duracao gravada, e nao de uma segunda conta.

    Regra 8 da spec 006: a duracao e calculada no envio e nao muda depois. Se o
    `eta` viesse de uma formula propria, ele e `duracao_minutos` poderiam
    divergir por um arredondamento, e o contador do professor terminaria num
    instante diferente do que a ficha da expedicao promete.
    """
    return inicio + timedelta(minutes=duracao_minutos)


def prever_despacho(
    *,
    treinador: TreinadorParaExpedicao,
    time: Sequence[PokemonNoTime],
    grafo: GrafoDeLocais,
    visitados: Collection[str],
    destino: LocalDaExpedicao,
    seed: int,
    agora: datetime,
    carga: Sequence[ItemNaCarga] = (),
    escala: float = 1.0,
) -> PreviaDoDespacho:
    """A mesma validacao do envio, com o erro devolvido em vez de levantado.

    E a funcao de `POST /expeditions/preview`: a tela precisa do motivo para
    exibir, nao de uma excecao para tratar.

    `LocalDesconhecido` nao e capturado de proposito. Pedir previa de um local
    que nao existe no mapa nao e uma escolha recusada e sim um 404, e
    devolve-lo como "invalido, motivo: nao existe" transformaria um erro de
    cliente numa resposta 200.
    """
    try:
        despacho = calcular_despacho(
            treinador=treinador,
            time=time,
            grafo=grafo,
            visitados=visitados,
            destino=destino,
            seed=seed,
            agora=agora,
            carga=carga,
            escala=escala,
        )
    except (ErroDeExpedicao, DestinoForaDeAlcance, ErroDeTime) as erro:
        return PreviaDoDespacho(
            valido=False,
            codigo=erro.codigo,
            motivo=str(erro),
            detalhes=dict(erro.detalhes),
        )
    return PreviaDoDespacho(valido=True, despacho=despacho)


def rota_do_despacho(
    grafo: GrafoDeLocais, visitados: Collection[str], destino_id: str
) -> RotaAteLocal:
    """A rota que o despacho vai usar, para quem precisa dela antes de validar o resto.

    Atalho nomeado para `mapa.exigir_destino_alcancavel`, que existe para que a
    camada de servico nao tenha de conhecer dois modulos do dominio so para
    montar a tela de escolha de destino.
    """
    return exigir_destino_alcancavel(grafo, visitados, destino_id)
