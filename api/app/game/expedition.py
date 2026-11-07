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
gravadas em `dificuldade_calculada` e exibidas ao professor, e a mesma conta
refeita a partir das colunas precisa dar o mesmo numero. O que elas **nao**
sao e o resultado de cada encontro: a resolucao da Fase 7 recalcula a chance
com o nivel selvagem efetivamente sorteado e o time no desgaste do momento, e
por isso o numero do despacho e uma estimativa — a interface o rotula assim, e
o relatorio guarda a chance de cada encontro para explicar a derrota.

A escala de tempo (`EXPEDITION_TIME_SCALE`, ADR-004) **multiplica** e e
ambiente, nao calibragem: nao esta em `balance.py` e nao e lida aqui dentro —
chega como argumento e segue para `mapa.duracao_estimada`.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum
from fractions import Fraction
from math import exp, floor
from typing import Any, ClassVar
from uuid import UUID

from app.game import balance, narrativa
from app.game.achados import achado_apos_vitoria
from app.game.aleatoriedade import GeradorAleatorio
from app.game.capture import (
    escolher_pokebola,
    nivel_medio_do_time,
    probabilidade_de_captura,
)
from app.game.cura import aplicar_cura, escolher_cura
from app.game.encounter import (
    LinhaDeEncontro,
    quantidade_de_encontros,
    sortear_especie,
    sortear_nivel,
)
from app.game.erros import ErroDeDominio
from app.game.evolucao import EspecieNoCatalogo, evolucoes_apos
from app.game.experience import (
    CurvaCrescimento,
    aplicar_experiencia,
    curva_de,
    experiencia_total_para_nivel,
)
from app.game.itens import ItemDaMochila, consumir
from app.game.mapa import (
    DestinoForaDeAlcance,
    GrafoDeLocais,
    RotaAteLocal,
    duracao_da_rota,
    exigir_destino_alcancavel,
)
from app.game.power import PokemonNoTime, poder_do_time, poder_pokemon, somar_stats_base
from app.game.stats import StatsBase
from app.game.team import ErroDeTime, capacidade_bagagem
from app.game.trainers import (
    DESCRICAO_DO_STATUS,
    StatusTreinador,
    experiencia_ganha_por_batalha,
)

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

    A Fase 7 chama esta mesma funcao para resolver cada encontro de verdade,
    mas **com outros argumentos**, e os dois numeros nao coincidem: aqui a
    dificuldade usa o nivel selvagem MEDIO do local e o time como partiu, e na
    resolucao ela usa o nivel efetivamente sorteado e o time no desgaste
    daquele momento. O numero do despacho e uma estimativa, a interface o
    rotula assim, e o relatorio guarda a chance de cada encontro no payload do
    evento para que a derrota continue explicavel.
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


# --- Resolucao: entrada (Fase 7, spec 007) ----------------------------------
#
# A partir daqui o modulo responde a terceira pergunta da expedicao: **o que
# aconteceu la fora?**. `resolver` e uma funcao pura — mesmo contexto e mesmo
# gerador semeado produzem exatamente o mesmo relatorio, evento a evento
# (criterio 3 da spec 007 e Artigo III). Nenhum estado vem de fora do
# argumento, nenhum relogio e lido, e o gerador chega pronto.
#
# A ORDEM DAS ROLAGENS E CONTRATO, fixada no plano da spec 007:
#
#   1  quantidade de encontros                    randint
#   para cada encontro:
#   2    especie                                  random (peso acumulado)
#   3    nivel do selvagem                        randint
#   4    vitoria ou derrota                       random
#        em caso de vitoria:
#   5      desgaste                               randint(3, 8)
#   6      houve achado                           random
#   7      qual item                              random (so se houve)
#   8      tentativa de captura                   random (so se ha tentativa)
#        em caso de derrota:
#   5'     desgaste                               randint(15, 30)
#
# Uma rolagem a mais, a menos ou trocada de lugar reescreve o resultado de
# TODA expedicao ja despachada e ainda nao resolvida — a semente esta gravada
# e o relatorio so existe quando o professor o reclama. O teste de ordem em
# `tests/test_game_resolucao.py` existe para quebrar ruidosamente nesse dia.
#
# A ordem dos EVENTOS e livre: ela e narrativa, nao mecanica. Por isso o
# desgaste e rolado antes de o evento `BATALHA` ser escrito — o payload do
# evento mostra quanto custou a vitoria sem que isso mova rolagem nenhuma.


class ContextoInvalido(ErroDeExpedicao):
    """O retrato do envio nao descreve uma expedicao resolvivel.

    Nao e jogada recusada e sim contexto montado errado pelo servico: especie
    fora do catalogo, time vazio, duracao negativa. Erro proprio para que o
    router nao o confunda com uma recusa de despacho.
    """

    codigo: ClassVar[str] = "CONTEXTO_INVALIDO"


@dataclass(frozen=True, slots=True)
class EspecieEmCampo:
    """Tudo que a resolucao precisa saber de uma especie do seed.

    Reune num objeto so o que cinco modulos do dominio pedem em separado: a
    `experiencia_base` da formula de experiencia (SDD 4.1), a `taxa_captura`
    da probabilidade de captura (SDD 4.6), a curva de crescimento, a soma dos
    stats-base que alimenta o poder (SDD 4.3) e o elo de evolucao.

    Nao e o `EspecieNoCatalogo` de `evolucao.py` nem o substitui: aquele e o
    minimo que a cadeia de evolucao precisa, e `_catalogo_para_evolucao`
    projeta este naquele. Duas dataclasses em vez de uma com campos opcionais
    porque `evolucao.py` nao tem por que conhecer taxa de captura.
    """

    id: int
    nome: str
    experiencia_base: int
    taxa_captura: int
    curva_crescimento: CurvaCrescimento | str
    soma_stats_base: int
    evolui_para_id: int | None = None
    evolui_em_nivel: int | None = None

    def __post_init__(self) -> None:
        curva_de(self.curva_crescimento)
        if self.experiencia_base < 0:
            raise ContextoInvalido(
                f"A especie {self.nome} ({self.id}) tem experiencia base negativa: "
                f"{self.experiencia_base}."
            )
        if self.soma_stats_base < 0:
            raise ContextoInvalido(
                f"A especie {self.nome} ({self.id}) tem soma de stats base negativa: "
                f"{self.soma_stats_base}."
            )

    @classmethod
    def a_partir_dos_stats(
        cls,
        *,
        id: int,
        nome: str,
        experiencia_base: int,
        taxa_captura: int,
        curva_crescimento: CurvaCrescimento | str,
        stats_base: StatsBase,
        evolui_para_id: int | None = None,
        evolui_em_nivel: int | None = None,
    ) -> EspecieEmCampo:
        """Atalho para quem tem os seis stats-base em maos, como o servico tem."""
        return cls(
            id=id,
            nome=nome,
            experiencia_base=experiencia_base,
            taxa_captura=taxa_captura,
            curva_crescimento=curva_crescimento,
            soma_stats_base=somar_stats_base(stats_base),
            evolui_para_id=evolui_para_id,
            evolui_em_nivel=evolui_em_nivel,
        )


CatalogoEmCampo = Mapping[int, EspecieEmCampo]


@dataclass(frozen=True, slots=True)
class PokemonDaExpedicao:
    """Um Pokemon do time, como ele partiu.

    Nao traz curva nem stats-base: os dois sao da ESPECIE e chegam pelo
    catalogo. Repeti-los aqui abriria a porta para um Pokemon cuja curva
    discorda da propria especie — e `aplicar_experiencia` recusa nivel que nao
    corresponde a experiencia, entao a divergencia so apareceria no meio da
    resolucao, com o professor esperando o relatorio.
    """

    id: UUID
    especie_id: int
    nivel: int
    experiencia: int
    hp_atual_pct: int


@dataclass(frozen=True, slots=True)
class TreinadorEmCampo:
    """O treinador do ponto de vista do relatorio.

    Separado de `TreinadorParaExpedicao` porque as duas perguntas sao
    diferentes: o despacho quer saber o `status` (ele pode sair?), e a
    resolucao quer saber o `nome` (quem assina o relatorio). Juntar as duas
    obrigaria o servico a carregar um campo inutil em cada chamada.
    """

    id: UUID
    nome: str
    nivel: int


@dataclass(frozen=True, slots=True)
class DestinoEmCampo:
    """O destino com o que a resolucao precisa, alem da dificuldade.

    Compoe `LocalDaExpedicao` em vez de repetir os campos dele: a faixa de
    nivel selvagem e o `nivel_dificuldade` ja sao validados la, e duplica-los
    criaria dois lugares onde o seed pode discordar de si mesmo.
    """

    local: LocalDaExpedicao
    nome: str
    encontros_base: int
    linhas_de_encontro: tuple[LinhaDeEncontro, ...]

    def __post_init__(self) -> None:
        if self.encontros_base < 0:
            raise ContextoInvalido(
                f"O destino {self.nome} declara encontros base negativo: {self.encontros_base}."
            )
        if not self.linhas_de_encontro:
            raise ContextoInvalido(
                f"O destino {self.nome} nao tem tabela de encontros, e sem ela a expedicao "
                "nao tem o que encontrar."
            )


@dataclass(frozen=True, slots=True)
class ContextoDeResolucao:
    """O retrato imutavel do envio: tudo que a resolucao pode olhar.

    O servico monta este objeto dentro da transacao, chama `resolver` e grava o
    que voltou. Nada aqui e lido do banco depois, e e isso que torna o
    criterio 3 testavel sem infraestrutura: o mesmo contexto com a mesma
    semente da o mesmo relatorio em qualquer maquina, hoje ou daqui a um ano.

    `linhas_de_encontro` ja chega na ordem canonica (`especie_id` crescente) —
    o sorteio por peso acumula na ordem recebida, e uma tabela em outra ordem
    muda o resultado da mesma semente. Quem monta o contexto garante a ordem
    com `ORDER BY especie_id`, ou passa por `encounter.ordenar_linhas`.

    `nomes_de_itens` existe para que o texto do evento `ITEM` possa dizer
    "Poke Ball" e nao "poke-ball": o achado sai de `balance.TABELA_DE_ACHADOS`,
    que so guarda identificadores, e pode nem estar na carga. Faltando o nome,
    o identificador aparece no lugar — um texto feio e melhor que uma
    resolucao derrubada.
    """

    treinador: TreinadorEmCampo
    time: tuple[PokemonDaExpedicao, ...]
    destino: DestinoEmCampo
    origem_nome: str
    catalogo: CatalogoEmCampo
    carga: tuple[ItemDaMochila, ...] = ()
    especies_vistas: frozenset[int] = frozenset()
    nomes_de_itens: Mapping[str, str] = field(default_factory=dict)
    duracao_minutos: int = 0

    def __post_init__(self) -> None:
        if not self.time:
            raise TimeVazio(
                "Esta expedicao partiu sem nenhum Pokemon no time, e sem time nao ha o que "
                "resolver.",
                detalhes={"treinador_id": str(self.treinador.id)},
            )
        capacidade_bagagem(len(self.time))
        if len({membro.id for membro in self.time}) != len(self.time):
            raise ContextoInvalido("O mesmo Pokemon aparece duas vezes no time da expedicao.")
        if self.duracao_minutos < 0:
            raise ContextoInvalido(
                f"A duracao da expedicao chegou negativa: {self.duracao_minutos} minutos."
            )
        for membro in self.time:
            _exigir_especie_no_catalogo(self.catalogo, membro.especie_id, "do time")
        for linha in self.destino.linhas_de_encontro:
            _exigir_especie_no_catalogo(self.catalogo, linha.especie_id, "da tabela de encontros")
        _exigir_cadeias_de_evolucao_coerentes(self.catalogo)

    @property
    def nivel_dificuldade(self) -> int:
        """Atalho para o numero que a dificuldade de cada encontro multiplica."""
        return self.destino.local.nivel_dificuldade


def _exigir_especie_no_catalogo(
    catalogo: CatalogoEmCampo, especie_id: int, origem: str
) -> EspecieEmCampo:
    especie = catalogo.get(especie_id)
    if especie is None:
        raise ContextoInvalido(
            f"A especie {especie_id} {origem} nao esta no catalogo do contexto, e sem ela a "
            "resolucao nao sabe nem o nome nem a experiencia base dela."
        )
    return especie


def _exigir_cadeias_de_evolucao_coerentes(catalogo: CatalogoEmCampo) -> None:
    """Toda evolucao presente no catalogo aponta para alguem e mantem a curva.

    A conferencia e feita na construcao do contexto, antes de qualquer
    escrita, e nao no meio do laco. O motivo e a curva: nivel e experiencia sao
    o mesmo numero lido de dois jeitos, e uma evolucao que trocasse a curva de
    crescimento faria o Pokemon gravado ficar com um nivel que a nova curva nao
    confirma — `aplicar_experiencia` recusaria esse Pokemon na expedicao
    SEGUINTE, longe da causa. O seed de Kanto nao tem nenhum caso assim; esta
    guarda existe para o dia em que tiver.
    """
    for especie in catalogo.values():
        if especie.evolui_para_id is None:
            continue
        proxima = catalogo.get(especie.evolui_para_id)
        if proxima is None:
            raise ContextoInvalido(
                f"A especie {especie.nome} ({especie.id}) evolui para "
                f"{especie.evolui_para_id}, que nao esta no catalogo do contexto."
            )
        if curva_de(proxima.curva_crescimento) is not curva_de(especie.curva_crescimento):
            raise ContextoInvalido(
                f"A especie {especie.nome} ({especie.id}) evolui para {proxima.nome} "
                f"({proxima.id}) e as duas tem curvas de crescimento diferentes "
                f"({especie.curva_crescimento} e {proxima.curva_crescimento}): a experiencia "
                "acumulada deixaria de corresponder ao nivel gravado."
            )


# --- Resolucao: saida -------------------------------------------------------


class TipoDeEvento(StrEnum):
    """Os tipos da linha do tempo, uniao fechada compartilhada com o frontend.

    Fechada de proposito (contratos de API do plano da spec 007): a tela
    desenha um icone por tipo, e um tipo novo chegando do servidor apareceria
    sem icone nenhum. Acrescentar um exige mexer nos dois lados no mesmo
    commit.

    `ITEM` significa item ACHADO em campo. O item CONSUMIDO — a Pocao gasta
    depois de uma derrota — vai no texto e no payload do `CONTRATEMPO`, pelo
    mesmo motivo: dois significados no mesmo tipo fariam a tela desenhar o
    icone de achado para uma Pocao que saiu da mochila.
    """

    PARTIDA = "PARTIDA"
    BATALHA = "BATALHA"
    CAPTURA = "CAPTURA"
    CAPTURA_FALHA = "CAPTURA_FALHA"
    DESCOBERTA = "DESCOBERTA"
    ITEM = "ITEM"
    CONTRATEMPO = "CONTRATEMPO"
    SUBIU_NIVEL = "SUBIU_NIVEL"
    EVOLUCAO = "EVOLUCAO"
    RETORNO = "RETORNO"


@dataclass(frozen=True, slots=True)
class EventoDeCampo:
    """Uma linha do relatorio: o que o professor le e o que a tela desenha.

    `texto` e para ler, `payload` e para renderizar. A separacao e deliberada:
    a interface nunca extrai numero de frase, e mudar a redacao na Fase 9 nao
    quebra tela nenhuma.
    """

    ordem: int
    tipo: TipoDeEvento
    texto: str
    ocorrido_em_minuto: int
    payload: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.ordem < 0:
            raise ContextoInvalido(f"A ordem de um evento nao pode ser negativa: {self.ordem}.")
        if self.ocorrido_em_minuto < 0:
            raise ContextoInvalido(
                f"Um evento nao acontece antes da partida: minuto {self.ocorrido_em_minuto}."
            )
        if len(self.texto) > balance.LIMITE_TEXTO_DO_EVENTO:
            raise narrativa.TextoLongoDemais(
                f"O texto do evento {self.tipo.value} tem {len(self.texto)} caracteres e o "
                f"limite da coluna e {balance.LIMITE_TEXTO_DO_EVENTO}."
            )


@dataclass(frozen=True, slots=True)
class PokemonAposExpedicao:
    """O antes e o depois de um Pokemon do time, pronto para o servico gravar.

    `especie_id` e a especie com que o Pokemon PARTIU; `evoluiu_para_id`, a que
    ele tem na volta, ou nulo. A coluna a gravar e `especie_final_id`, que ja
    resolve os dois casos — assim o servico nao precisa repetir o `if`.
    """

    pokemon_id: UUID
    especie_id: int
    especie_nome: str
    nivel_antes: int
    nivel_depois: int
    experiencia_antes: int
    experiencia_depois: int
    hp_antes_pct: int
    hp_depois_pct: int
    evoluiu_para_id: int | None = None
    evoluiu_para_nome: str | None = None

    @property
    def experiencia_ganha(self) -> int:
        """O que de fato entrou, ja descontado o excedente do nivel 100."""
        return self.experiencia_depois - self.experiencia_antes

    @property
    def especie_final_id(self) -> int:
        """A especie a gravar: a nova, se evoluiu, senao a de sempre."""
        return self.evoluiu_para_id if self.evoluiu_para_id is not None else self.especie_id

    @property
    def subiu_de_nivel(self) -> bool:
        return self.nivel_depois > self.nivel_antes


@dataclass(frozen=True, slots=True)
class CapturaEmCampo:
    """Um Pokemon que vem para o laboratorio, com tudo que a linha nova precisa.

    `experiencia` vem junto e nao e opcional: `aplicar_experiencia` RECUSA um
    Pokemon cujo nivel nao corresponda a experiencia gravada, entao um
    capturado que nascesse com nivel 7 e experiencia 0 derrubaria a PROXIMA
    expedicao dele. O dominio entrega o par ja coerente para que o servico nao
    tenha como errar.

    `hp_atual_pct` vem cheio: o selvagem capturado chega descansado ao
    laboratorio, e a enfermaria da recuperacao passiva (SDD 4.8) nao tem nada
    a fazer com ele.
    """

    especie_id: int
    especie_nome: str
    nivel: int
    experiencia: int
    hp_atual_pct: int
    ordem_do_encontro: int


@dataclass(frozen=True, slots=True)
class ItemDoRelatorio:
    """Um item consumido em campo ou achado em campo, ja somado por identificador."""

    item_id: str
    nome: str
    quantidade: int


@dataclass(frozen=True, slots=True)
class AvistamentoEmCampo:
    """O que a Pokedex aprende desta expedicao sobre uma especie.

    `primeira_vez` diz se houve `DESCOBERTA`; `vezes` e quantos encontros desta
    expedicao foram com ela, que e o numero que o avistamento soma (regra 12 e
    criterio 18 da spec 007).
    """

    especie_id: int
    especie_nome: str
    vezes: int
    primeira_vez: bool


@dataclass(frozen=True, slots=True)
class RelatorioDeCampo:
    """Tudo que o servico precisa gravar, e nada que ele precise recalcular.

    O status so pode ser `CONCLUIDA_SUCESSO` ou `CONCLUIDA_FALHA`: a resolucao
    sempre termina a expedicao. `ABORTADA` e decisao do professor, nao
    resultado de campo.

    Numa falha, `capturas` vem VAZIA (regra 16 da spec 007) mesmo que a linha
    do tempo tenha eventos `CAPTURA`: o Pokemon foi capturado em campo e se
    perdeu na fuga, e o texto do `RETORNO` diz isso. O que a falha preserva e
    a experiencia ganha nas batalhas vencidas antes dela, os avistamentos e os
    itens achados; o que ela nao da e captura, desbloqueio e experiencia de
    laboratorio.
    """

    status: StatusExpedicao
    eventos: tuple[EventoDeCampo, ...]
    time: tuple[PokemonAposExpedicao, ...]
    capturas: tuple[CapturaEmCampo, ...]
    itens_consumidos: tuple[ItemDoRelatorio, ...]
    itens_encontrados: tuple[ItemDoRelatorio, ...]
    avistamentos: tuple[AvistamentoEmCampo, ...]
    experiencia_treinador: int
    experiencia_laboratorio: int
    encontros: int
    vitorias: int
    derrotas: int
    duracao_efetiva_minutos: int

    @property
    def sucesso(self) -> bool:
        return self.status is StatusExpedicao.CONCLUIDA_SUCESSO

    @property
    def desbloqueia_destino(self) -> bool:
        """Regra 15 e 16 da spec 007: so o sucesso desbloqueia o destino.

        Se o local JA estava desbloqueado e assunto de quem grava — o dominio
        nao recebe a lista de visitados na resolucao e nao tem como saber.
        """
        return self.sucesso


# --- Resolucao: estado interno do laco --------------------------------------


@dataclass(frozen=True, slots=True)
class _EstadoDoMembro:
    """O Pokemon do time durante a expedicao, substituido a cada mudanca.

    Imutavel como todo o resto: cada desgaste, cada ganho de experiencia e cada
    evolucao produzem um estado novo com `replace`. Guardar o inicial ao lado
    do corrente e o que permite montar o antes-e-depois do relatorio sem o
    servico ter de lembrar de nada.
    """

    pokemon_id: UUID
    especie: EspecieEmCampo
    especie_inicial: EspecieEmCampo
    nivel: int
    experiencia: int
    hp_atual_pct: int
    nivel_inicial: int
    experiencia_inicial: int
    hp_inicial_pct: int

    @property
    def no_time(self) -> PokemonNoTime:
        """A visao que `power.py` e `cura.py` tem deste Pokemon agora."""
        return PokemonNoTime(
            nivel=self.nivel,
            soma_stats_base=self.especie.soma_stats_base,
            hp_atual_pct=self.hp_atual_pct,
        )

    @property
    def evoluiu(self) -> bool:
        return self.especie.id != self.especie_inicial.id

    def no_relatorio(self) -> PokemonAposExpedicao:
        return PokemonAposExpedicao(
            pokemon_id=self.pokemon_id,
            especie_id=self.especie_inicial.id,
            especie_nome=self.especie_inicial.nome,
            nivel_antes=self.nivel_inicial,
            nivel_depois=self.nivel,
            experiencia_antes=self.experiencia_inicial,
            experiencia_depois=self.experiencia,
            hp_antes_pct=self.hp_inicial_pct,
            hp_depois_pct=self.hp_atual_pct,
            evoluiu_para_id=self.especie.id if self.evoluiu else None,
            evoluiu_para_nome=self.especie.nome if self.evoluiu else None,
        )


def _membros_iniciais(contexto: ContextoDeResolucao) -> tuple[_EstadoDoMembro, ...]:
    membros: list[_EstadoDoMembro] = []
    for pokemon in contexto.time:
        especie = _exigir_especie_no_catalogo(contexto.catalogo, pokemon.especie_id, "do time")
        membros.append(
            _EstadoDoMembro(
                pokemon_id=pokemon.id,
                especie=especie,
                especie_inicial=especie,
                nivel=pokemon.nivel,
                experiencia=pokemon.experiencia,
                hp_atual_pct=pokemon.hp_atual_pct,
                nivel_inicial=pokemon.nivel,
                experiencia_inicial=pokemon.experiencia,
                hp_inicial_pct=pokemon.hp_atual_pct,
            )
        )
        # Calcula o poder uma vez agora, e joga fora: a conta valida nivel, hp
        # e stats (Artigo VI), e um dado fora de faixa deve reclamar na entrada
        # e nao no meio do quarto encontro, com o professor esperando.
        poder_pokemon(membros[-1].no_time)
    return tuple(membros)


def _catalogo_para_evolucao(catalogo: CatalogoEmCampo) -> dict[int, EspecieNoCatalogo]:
    """Projeta o catalogo da resolucao no que `evolucao.py` pede."""
    return {
        especie_id: EspecieNoCatalogo(
            id=especie.id,
            nome=especie.nome,
            evolui_para_id=especie.evolui_para_id,
            evolui_em_nivel=especie.evolui_em_nivel,
        )
        for especie_id, especie in catalogo.items()
    }


def _anotar(
    eventos: list[EventoDeCampo],
    tipo: TipoDeEvento,
    minuto: int,
    texto: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Acrescenta o evento com `ordem` igual a posicao dele na linha do tempo.

    A ordem e a posicao, e nao um contador a parte, porque dois contadores que
    deveriam andar juntos sempre acabam discordando — e aqui a discordancia
    apareceria como linha do tempo embaralhada na tela do professor.
    """
    eventos.append(
        EventoDeCampo(
            ordem=len(eventos),
            tipo=tipo,
            texto=texto,
            ocorrido_em_minuto=minuto,
            payload=payload,
        )
    )


def minuto_do_encontro(duracao_minutos: int, indice: int, quantidade: int) -> int:
    """Distribui os encontros ao longo da duracao gravada da expedicao.

    Os encontros caem em intervalos iguais ENTRE a partida e o retorno: com
    duracao 60 e tres encontros, eles acontecem nos minutos 15, 30 e 45. Nem a
    partida nem o retorno disputam lugar com um encontro, que e o que a
    divisao por `quantidade + 1` garante.

    Divisao inteira: o minuto e o que a tela mostra a esquerda da linha do
    tempo, e meio minuto nao e informacao para ninguem.
    """
    if quantidade < 1:
        raise ContextoInvalido(f"Uma expedicao tem ao menos um encontro; vieram {quantidade}.")
    return duracao_minutos * (indice + 1) // (quantidade + 1)


def experiencia_de_batalha(experiencia_base: int, nivel_derrotado: int) -> int:
    """`experiencia_base * nivel_derrotado // DIVISOR_EXP` (SDD 4.1).

    A divisao inteira trunca de proposito: experiencia e contador, nao medida.
    """
    if experiencia_base < 0:
        raise ContextoInvalido(f"A experiencia base chegou negativa: {experiencia_base}.")
    return experiencia_base * nivel_derrotado // balance.DIVISOR_EXP


def experiencia_de_laboratorio(nivel_dificuldade: int) -> int:
    """`EXP_LAB_POR_EXPEDICAO * (1 + nivel_dificuldade * BONUS)` (SDD 4.1).

    So o sucesso paga (regra 15 da spec 007); a falha devolve zero. A conta
    corre em racional exato e e truncada uma unica vez, no fim, pelo mesmo
    motivo de `power.py`: a calibragem da Fase 9 nao deve mudar o resultado por
    um arredondamento intermediario.
    """
    if nivel_dificuldade < 0:
        raise LocalInvalido(f"O nivel de dificuldade chegou negativo: {nivel_dificuldade}.")
    bonus = 1 + nivel_dificuldade * _fracao(balance.BONUS_EXP_LAB_POR_DIFICULDADE)
    return floor(balance.EXP_LAB_POR_EXPEDICAO * bonus)


def dificuldade_do_encontro(nivel_selvagem: int, nivel_dificuldade_local: int) -> float:
    """A dificuldade do encontro que de fato aconteceu (SDD 4.3).

    Difere da `dificuldade_do_local` gravada no despacho em um ponto que muda
    tudo: ali o nivel selvagem e a MEDIA da faixa do local, aqui e o nivel
    efetivamente sorteado. Um Caterpie de nivel 3 e um de nivel 7 saem do mesmo
    local com dificuldades diferentes, e e por isso que a chance do despacho e
    estimativa e a chance de cada encontro vai no payload do evento.
    """
    bruta = nivel_selvagem * nivel_dificuldade_local * _fracao(balance.FATOR_DIFICULDADE)
    return _arredondar(bruta, balance.CASAS_DECIMAIS_DIFICULDADE)


def _lider(membros: Sequence[_EstadoDoMembro]) -> str:
    """O nome que a narrativa poe na frente da linha.

    O primeiro Pokemon de pe, ou o primeiro do time quando todos cairam. Nao
    tem efeito mecanico nenhum: a chance sai do poder do time inteiro
    (ADR-003), e este nome serve so para a frase nao ser impessoal.
    """
    for membro in membros:
        if membro.hp_atual_pct > 0:
            return membro.especie.nome
    return membros[0].especie.nome


def _desgastar(membros: Sequence[_EstadoDoMembro], pontos: int) -> tuple[_EstadoDoMembro, ...]:
    """Tira os mesmos pontos de hp de todo o time, com piso em zero.

    Piso e nao negativo: `hp_atual_pct` e contador de 0 a 100, e um nocauteado
    nao fica mais nocauteado. Quem ja estava em zero continua em zero, e
    continua contando como participante na divisao de experiencia — ele estava
    la.
    """
    return tuple(
        replace(membro, hp_atual_pct=max(0, membro.hp_atual_pct - pontos)) for membro in membros
    )


def _ganhar_experiencia(
    membro: _EstadoDoMembro,
    ganho: int,
    catalogo: CatalogoEmCampo,
    catalogo_de_evolucao: Mapping[int, EspecieNoCatalogo],
    eventos: list[EventoDeCampo],
    minuto: int,
) -> _EstadoDoMembro:
    """Aplica o ganho a um Pokemon e escreve o que isso produziu.

    Um `SUBIU_NIVEL` quando o nivel mudou — nunca quando nao mudou, inclusive
    no nivel 100, onde a experiencia excedente e descartada (criterio 12 da
    spec 007). Depois, um `EVOLUCAO` por etapa da cadeia que o novo nivel
    dispara: a cadeia encadeia, e um salto do nivel 15 ao 33 produz os dois
    eventos, em ordem (criterio 11).

    Nada aqui consome o gerador. Experiencia, nivel e evolucao sao
    deterministicos, e e por isso que eles nao aparecem na ordem das rolagens.
    """
    resultado = aplicar_experiencia(
        membro.especie.curva_crescimento, membro.nivel, membro.experiencia, ganho
    )
    atual = replace(membro, nivel=resultado.nivel_depois, experiencia=resultado.experiencia_depois)
    if resultado.subiu:
        _anotar(
            eventos,
            TipoDeEvento.SUBIU_NIVEL,
            minuto,
            narrativa.texto_de_subiu_nivel(
                len(eventos),
                pokemon=atual.especie.nome,
                antes=resultado.nivel_antes,
                depois=resultado.nivel_depois,
            ),
            {
                "pokemon_id": str(atual.pokemon_id),
                "especie_id": atual.especie.id,
                "especie_nome": atual.especie.nome,
                "nivel_antes": resultado.nivel_antes,
                "nivel_depois": resultado.nivel_depois,
                "experiencia": resultado.experiencia_depois,
                "experiencia_ganha": resultado.experiencia_aplicada,
            },
        )
    for elo in evolucoes_apos(atual.especie.id, atual.nivel, catalogo_de_evolucao):
        anterior = atual.especie
        proxima = _exigir_especie_no_catalogo(catalogo, elo.id, "da cadeia de evolucao")
        atual = replace(atual, especie=proxima)
        _anotar(
            eventos,
            TipoDeEvento.EVOLUCAO,
            minuto,
            narrativa.texto_de_evolucao(len(eventos), antes=anterior.nome, depois=proxima.nome),
            {
                "pokemon_id": str(atual.pokemon_id),
                "especie_id_antes": anterior.id,
                "especie_nome_antes": anterior.nome,
                "especie_id": proxima.id,
                "especie_nome": proxima.nome,
                "nivel": atual.nivel,
            },
        )
    return atual


def _nome_do_item(contexto: ContextoDeResolucao, item_id: str) -> str:
    """O nome de exibicao do item, com o identificador como ultimo recurso."""
    for item in contexto.carga:
        if item.item_id == item_id:
            return item.nome
    return contexto.nomes_de_itens.get(item_id, item_id)


def _somados(
    quantidades: Mapping[str, int], contexto: ContextoDeResolucao
) -> tuple[ItemDoRelatorio, ...]:
    """Transforma o acumulado por identificador em linhas ordenadas do relatorio.

    Ordenado por `item_id` porque o servico trava as linhas de estoque nessa
    ordem para nao abracar deadlock com outra resolucao concorrente — mesma
    razao de `DespachoCalculado.debitos`.
    """
    return tuple(
        ItemDoRelatorio(item_id=item_id, nome=_nome_do_item(contexto, item_id), quantidade=total)
        for item_id, total in sorted(quantidades.items())
        if total > 0
    )


# --- Resolucao: o laco ------------------------------------------------------


def resolver(contexto: ContextoDeResolucao, gerador: GeradorAleatorio) -> RelatorioDeCampo:
    """Resolve a expedicao inteira e devolve o relatorio de campo.

    Funcao pura: mesmo contexto e mesmo gerador semeado produzem byte a byte o
    mesmo relatorio, evento a evento (criterio 3 da spec 007, invariante 19 e
    Artigo III). O gerador chega semeado de fora, o relogio nao e lido e nada
    e persistido aqui — quem grava e o servico, com o que esta no retorno.

    **A chance muda a cada encontro.** O poder do time e recalculado no inicio
    de cada iteracao, com o hp do momento, e a dificuldade usa o nivel
    efetivamente sorteado. O quinto encontro e mais duro que o primeiro porque
    o time chega nele machucado — e isso e mecanica, nao detalhe: e o que faz
    expedicao longa ser uma aposta.

    **Time inteiro a zero nao divide por zero.** O poder vai a zero, a razao
    poder/dificuldade vai a zero e a sigmoide entrega o piso de
    `P_VITORIA_MINIMA`: a expedicao provavelmente falha por tres derrotas, que
    e o desenho funcionando. O unico divisor do caminho e a dificuldade, e
    `chance_estimada` ja trata dificuldade zero devolvendo o teto.

    **A captura para, o registro continua.** Atingida a capacidade da bagagem
    ou acabadas as Pokebolas, nao ha mais tentativa — mas todo encontro
    seguinte continua virando avistamento na Pokedex (invariante 11, criterio
    7 da spec 007).
    """
    eventos: list[EventoDeCampo] = []
    membros = _membros_iniciais(contexto)
    catalogo_de_evolucao = _catalogo_para_evolucao(contexto.catalogo)
    carga = tuple(contexto.carga)

    consumidos: dict[str, int] = {}
    encontrados: dict[str, int] = {}
    capturas: list[CapturaEmCampo] = []
    vezes_vista: dict[int, int] = {}
    descobertas: set[int] = set()

    experiencia_treinador = 0
    vitorias = 0
    derrotas = 0
    derrotas_sem_cura = 0
    status = StatusExpedicao.CONCLUIDA_SUCESSO

    _anotar(
        eventos,
        TipoDeEvento.PARTIDA,
        0,
        narrativa.texto_de_partida(
            len(eventos),
            treinador=contexto.treinador.nome,
            origem=contexto.origem_nome,
            destino=contexto.destino.nome,
        ),
    )

    # Rolagem 1: quantos encontros esta expedicao teve.
    quantidade = quantidade_de_encontros(contexto.destino.encontros_base, gerador)
    minuto = 0

    for indice in range(quantidade):
        minuto = minuto_do_encontro(contexto.duracao_minutos, indice, quantidade)

        # Rolagens 2 e 3: com quem foi o encontro, e de que nivel.
        linha = sortear_especie(contexto.destino.linhas_de_encontro, gerador)
        nivel_selvagem = sortear_nivel(linha, gerador)
        especie = _exigir_especie_no_catalogo(
            contexto.catalogo, linha.especie_id, "da tabela de encontros"
        )

        vezes_vista[especie.id] = vezes_vista.get(especie.id, 0) + 1
        if especie.id not in contexto.especies_vistas and especie.id not in descobertas:
            descobertas.add(especie.id)
            _anotar(
                eventos,
                TipoDeEvento.DESCOBERTA,
                minuto,
                narrativa.texto_de_descoberta(
                    len(eventos), especie=especie.nome, local=contexto.destino.nome
                ),
                {
                    "especie_id": especie.id,
                    "especie_nome": especie.nome,
                    "local_id": contexto.destino.local.id,
                },
            )

        dificuldade = dificuldade_do_encontro(nivel_selvagem, contexto.nivel_dificuldade)
        poder = poder_do_time([membro.no_time for membro in membros], contexto.treinador.nivel)
        chance = chance_estimada(poder, dificuldade)
        lider = _lider(membros)

        # Rolagem 4: venceu ou perdeu.
        venceu = gerador.random() < chance

        if venceu:
            vitorias += 1
            exp_da_batalha = experiencia_de_batalha(especie.experiencia_base, nivel_selvagem)
            exp_por_pokemon = exp_da_batalha // len(membros)
            experiencia_treinador += experiencia_ganha_por_batalha(exp_da_batalha)

            # Rolagem 5: o desgaste da vitoria, igual para todo o time.
            desgaste = gerador.randint(*balance.DESGASTE_VITORIA)
            membros = _desgastar(membros, desgaste)

            _anotar(
                eventos,
                TipoDeEvento.BATALHA,
                minuto,
                narrativa.texto_de_batalha(
                    len(eventos), lider=lider, especie=especie.nome, nivel=nivel_selvagem
                ),
                {
                    "especie_id": especie.id,
                    "especie_nome": especie.nome,
                    "nivel_selvagem": nivel_selvagem,
                    "venceu": True,
                    "chance": chance,
                    "poder_time": poder,
                    "dificuldade": dificuldade,
                    "exp_da_batalha": exp_da_batalha,
                    "exp_por_pokemon": exp_por_pokemon,
                    "desgaste": desgaste,
                },
            )

            membros = tuple(
                _ganhar_experiencia(
                    membro,
                    exp_por_pokemon,
                    contexto.catalogo,
                    catalogo_de_evolucao,
                    eventos,
                    minuto,
                )
                for membro in membros
            )

            # Rolagens 6 e 7: houve achado e, havendo, qual item.
            achado = achado_apos_vitoria(contexto.nivel_dificuldade, gerador)
            if achado is not None:
                encontrados[achado.item_id] = encontrados.get(achado.item_id, 0) + achado.quantidade
                _anotar(
                    eventos,
                    TipoDeEvento.ITEM,
                    minuto,
                    narrativa.texto_de_item(
                        len(eventos),
                        item=_nome_do_item(contexto, achado.item_id),
                        quantidade=achado.quantidade,
                        local=contexto.destino.nome,
                    ),
                    {
                        "item_id": achado.item_id,
                        "item_nome": _nome_do_item(contexto, achado.item_id),
                        "quantidade": achado.quantidade,
                    },
                )

            # Rolagem 8: a tentativa de captura, se restar bola e espaco.
            #
            # Os dois limites da regra 10 sao checados SEPARADAMENTE, e e de
            # proposito. A municao esta na carga, que ja encolhe a cada
            # arremesso — `escolher_pokebola` devolve None quando acabou. A
            # vaga esta nas capturas feitas contra a capacidade da bagagem,
            # que nao muda durante a expedicao. Medir os dois com uma conta so
            # (`min(bolas, capacidade) > len(capturas)`) desconta a bola gasta
            # duas vezes — uma dentro do minimo e outra na comparacao — e faz
            # a ultima bola nunca ser arremessada.
            bola = escolher_pokebola(carga)
            ha_espaco = len(capturas) < capacidade_bagagem(len(membros))
            if bola is not None and ha_espaco:
                chance_captura = probabilidade_de_captura(
                    especie.taxa_captura,
                    bola.potencia,
                    nivel_medio_do_time([membro.nivel for membro in membros]),
                    nivel_selvagem,
                )
                capturou = gerador.random() < chance_captura
                carga = consumir(carga, bola.item_id)
                consumidos[bola.item_id] = consumidos.get(bola.item_id, 0) + 1
                payload_da_captura = {
                    "especie_id": especie.id,
                    "especie_nome": especie.nome,
                    "nivel": nivel_selvagem,
                    "bola_id": bola.item_id,
                    "bola_nome": bola.nome,
                    "chance": chance_captura,
                }
                if capturou:
                    capturas.append(
                        CapturaEmCampo(
                            especie_id=especie.id,
                            especie_nome=especie.nome,
                            nivel=nivel_selvagem,
                            experiencia=experiencia_total_para_nivel(
                                especie.curva_crescimento, nivel_selvagem
                            ),
                            hp_atual_pct=balance.BASE_PERCENTUAL,
                            ordem_do_encontro=indice,
                        )
                    )
                    _anotar(
                        eventos,
                        TipoDeEvento.CAPTURA,
                        minuto,
                        narrativa.texto_de_captura(
                            len(eventos),
                            especie=especie.nome,
                            nivel=nivel_selvagem,
                            bola=bola.nome,
                        ),
                        payload_da_captura,
                    )
                else:
                    _anotar(
                        eventos,
                        TipoDeEvento.CAPTURA_FALHA,
                        minuto,
                        narrativa.texto_de_captura_falha(
                            len(eventos),
                            especie=especie.nome,
                            nivel=nivel_selvagem,
                            bola=bola.nome,
                        ),
                        payload_da_captura,
                    )
            continue

        derrotas += 1
        derrotas_sem_cura += 1

        # Rolagem 5-alternativa: a derrota desgasta mais.
        desgaste = gerador.randint(*balance.DESGASTE_DERROTA)
        membros = _desgastar(membros, desgaste)

        # A cura vem DEPOIS do desgaste, que e quando ha o que curar, e nao
        # consome rolagem nenhuma: `escolher_cura` e deterministica de
        # proposito, para nao deslocar os sorteios seguintes.
        remedio = escolher_cura(carga, [membro.no_time for membro in membros])
        if remedio is not None:
            carga = consumir(carga, remedio.item_id)
            consumidos[remedio.item_id] = consumidos.get(remedio.item_id, 0) + 1
            curados = aplicar_cura(remedio, [membro.no_time for membro in membros])
            membros = tuple(
                replace(membro, hp_atual_pct=curado.hp_atual_pct)
                for membro, curado in zip(membros, curados, strict=True)
            )
            # Regra 9 da spec 007: a falha e por tres derrotas SEM o que curar.
            derrotas_sem_cura = 0

        _anotar(
            eventos,
            TipoDeEvento.CONTRATEMPO,
            minuto,
            narrativa.texto_de_contratempo(
                len(eventos),
                lider=lider,
                especie=especie.nome,
                nivel=nivel_selvagem,
                desgaste=desgaste,
                item_usado=None if remedio is None else remedio.nome,
            ),
            {
                "especie_id": especie.id,
                "especie_nome": especie.nome,
                "nivel_selvagem": nivel_selvagem,
                "venceu": False,
                "chance": chance,
                "poder_time": poder,
                "dificuldade": dificuldade,
                "desgaste": desgaste,
                "item_usado": None if remedio is None else remedio.item_id,
                "item_usado_nome": None if remedio is None else remedio.nome,
                "derrotas_sem_cura": derrotas_sem_cura,
            },
        )

        if derrotas_sem_cura >= balance.DERROTAS_PARA_FALHAR:
            status = StatusExpedicao.CONCLUIDA_FALHA
            break

    sucesso = status is StatusExpedicao.CONCLUIDA_SUCESSO
    # Numa falha o treinador volta mais cedo: o retorno acontece no minuto do
    # encontro que encerrou a expedicao, e nao no fim da duracao contratada.
    minuto_do_retorno = contexto.duracao_minutos if sucesso else minuto
    encontros_havidos = vitorias + derrotas

    # Regra 16 e criterio 15 da spec 007: expedicao falha nao traz captura
    # nenhuma. Os eventos `CAPTURA` continuam na linha do tempo porque a
    # captura ACONTECEU em campo — o que nao aconteceu foi a chegada ao
    # laboratorio —, e o texto do retorno diz isso com todas as letras para
    # que o resumo vazio nao pareca defeito. As Pokebolas gastas nessas
    # tentativas continuam gastas: elas foram arremessadas.
    capturas_mantidas = tuple(capturas) if sucesso else ()
    capturas_perdidas = 0 if sucesso else len(capturas)

    _anotar(
        eventos,
        TipoDeEvento.RETORNO,
        minuto_do_retorno,
        narrativa.texto_de_retorno(
            len(eventos),
            treinador=contexto.treinador.nome,
            sucesso=sucesso,
            encontros=encontros_havidos,
            vitorias=vitorias,
            derrotas_sem_cura=derrotas_sem_cura,
            capturas_perdidas=capturas_perdidas,
        ),
        {
            "status": status.value,
            "encontros": encontros_havidos,
            "vitorias": vitorias,
            "derrotas": derrotas,
            "derrotas_sem_cura": derrotas_sem_cura,
            "capturas": len(capturas_mantidas),
            "capturas_perdidas": capturas_perdidas,
        },
    )

    return RelatorioDeCampo(
        status=status,
        eventos=tuple(eventos),
        time=tuple(membro.no_relatorio() for membro in membros),
        capturas=capturas_mantidas,
        itens_consumidos=_somados(consumidos, contexto),
        itens_encontrados=_somados(encontrados, contexto),
        avistamentos=tuple(
            AvistamentoEmCampo(
                especie_id=especie_id,
                especie_nome=contexto.catalogo[especie_id].nome,
                vezes=vezes,
                primeira_vez=especie_id in descobertas,
            )
            for especie_id, vezes in sorted(vezes_vista.items())
        ),
        experiencia_treinador=experiencia_treinador,
        experiencia_laboratorio=(
            experiencia_de_laboratorio(contexto.nivel_dificuldade) if sucesso else 0
        ),
        encontros=encontros_havidos,
        vitorias=vitorias,
        derrotas=derrotas,
        duracao_efetiva_minutos=minuto_do_retorno,
    )
