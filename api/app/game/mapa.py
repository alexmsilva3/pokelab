"""Mapa de Kanto: alcance, rotas otimas e duracao estimada (spec 005, SDD 4.4).

Este modulo responde as tres perguntas que a escolha de um destino exige: para
onde da para ir, de onde se parte e quanto tempo a ida custa.

**A busca e Dijkstra, nao busca em largura.** O custo de atravessar um local
depende do tipo dele — cidade 3 minutos, rota 4, masmorra 8 —, entao o caminho
com menos arestas nao e necessariamente o mais rapido. No mapa linear de dez
nos da v1 as duas buscas quase sempre concordam, e e exatamente por isso que o
erro seria silencioso: um atalho por duas masmorras custa 16 minutos e perde
para um desvio por tres cidades, que custa 9, embora o desvio atravesse um
local a mais. So um grafo com essa forma mostra a diferenca, e ele esta em
`tests/test_game_mapa.py`.

**A busca e multi-origem.** Todos os locais ja visitados entram na fila com
custo zero, porque o treinador pode partir de qualquer um deles — nao e uma
busca a partir de Pallet Town. E dai que vem a promessa do SDD de que
desbloquear um local encurta de verdade as expedicoes: Mt. Moon partindo de
Pallet custa 55 minutos; com Route 3 ja visitada, 29.

`rotas_otimas` roda a busca **uma vez** e devolve o mapa inteiro. Montar uma
tela com uma busca por destino seriam dez buscas para responder uma pergunta
so.

Quatro decisoes de desenho valem o comentario.

A primeira: **o custo mora no no, nao na aresta**. `custo_travessia_minutos` e
do local, e o SDD 4.4 soma o custo de cada local do caminho **exceto a
origem** — entrar no destino custa o custo do destino. A formulacao de aresta
daria o mesmo numero neste seed e divergiria no primeiro local com custo
assimetrico.

A segunda: **o desempate e pelo caminho, nao pela ordem de iteracao**. A fila
compara `(custo, caminho)`, e o caminho e uma tupla de ids: dois caminhos de
mesmo custo sempre resolvem para o mesmo, independentemente da ordem em que os
locais chegaram e sem depender de ordem de iteracao de `set`, que varia entre
processos (Artigo III).

A terceira: **nenhum modelo ORM atravessa esta fronteira**. O grafo chega em
dataclasses enxutas, como em `team.py` e `kit_inicial.py`, e o Artigo I nao
sobreviveria a um `Local` do SQLAlchemy aqui dentro.

A quarta: **a escala de tempo e parametro**. `EXPEDITION_TIME_SCALE` e
ambiente, nao calibragem (ADR-004), e por isso nao esta em `balance.py` nem e
lida daqui — ela chega como argumento, como manda o Artigo I.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from fractions import Fraction
from heapq import heappop, heappush
from typing import Any, ClassVar

from app.game import balance
from app.game.erros import ErroDeDominio
from app.game.trainers import exigir_nivel_de_treinador

# --- Erros (Artigo VI) ------------------------------------------------------


class ErroDeMapa(ErroDeDominio):
    """Raiz das recusas do mapa.

    O `codigo` e o mesmo do contrato de API, declarado uma vez aqui para que o
    router nao tenha a propria tabela de traducao, como ja se faz em `team.py`.
    """

    codigo: ClassVar[str] = "MAPA_INVALIDO"

    def __init__(self, mensagem: str, *, detalhes: dict[str, Any] | None = None) -> None:
        self.detalhes = detalhes or {}
        super().__init__(mensagem)


class GrafoInvalido(ErroDeMapa):
    """O grafo recebido nao descreve um mapa percorrivel."""

    codigo: ClassVar[str] = "GRAFO_INVALIDO"


class LocalDesconhecido(ErroDeMapa):
    """O local pedido nao existe no mapa (criterio 10 da spec 005: 404)."""

    codigo: ClassVar[str] = "LOCAL_DESCONHECIDO"


class DestinoForaDeAlcance(ErroDeMapa):
    """Invariante 6 do SDD 3.3: o destino nao e vizinho de local desbloqueado."""

    codigo: ClassVar[str] = "DESTINO_FORA_DE_ALCANCE"


class ParametroDeDuracaoInvalido(ErroDeMapa):
    """Um dos numeros que alimentam a formula da duracao nao e utilizavel."""

    codigo: ClassVar[str] = "DURACAO_INVALIDA"


# --- Entrada ---------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LocalNoGrafo:
    """O minimo que o mapa precisa saber de um local.

    `custo_travessia_minutos` e `encontros_base` vem do seed; `vizinhos` sao as
    arestas do grafo de vizinhanca (SDD 3.1). Tipo, dificuldade e faixa de
    nivel selvagem nao entram: nada aqui depende deles, e o custo ja chega
    resolvido pelo seed.
    """

    id: str
    custo_travessia_minutos: int
    encontros_base: int
    vizinhos: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GrafoDeLocais:
    """Os locais do mapa e suas ligacoes, validados na construcao.

    A validacao acontece aqui, e nao a cada busca, porque um grafo corrompido
    nao e jogada possivel: e seed errado, e errar cedo mostra o problema em vez
    de transformar um vizinho com nome trocado num local inalcancavel para
    sempre, que ninguem nota.
    """

    locais: tuple[LocalNoGrafo, ...]
    _por_id: dict[str, LocalNoGrafo] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        por_id: dict[str, LocalNoGrafo] = {}
        for local in self.locais:
            if local.id in por_id:
                raise GrafoInvalido(
                    f"O local {local.id!r} aparece duas vezes no mapa.",
                    detalhes={"local_id": local.id},
                )
            if local.custo_travessia_minutos < 0:
                raise GrafoInvalido(
                    f"O local {local.id!r} tem custo de travessia negativo: "
                    f"{local.custo_travessia_minutos}.",
                    detalhes={"local_id": local.id},
                )
            if local.encontros_base < 0:
                raise GrafoInvalido(
                    f"O local {local.id!r} tem numero de encontros negativo: "
                    f"{local.encontros_base}.",
                    detalhes={"local_id": local.id},
                )
            por_id[local.id] = local
        for local in self.locais:
            for vizinho_id in local.vizinhos:
                if vizinho_id not in por_id:
                    raise GrafoInvalido(
                        f"O local {local.id!r} aponta para o vizinho inexistente {vizinho_id!r}.",
                        detalhes={"local_id": local.id, "vizinho_id": vizinho_id},
                    )
        object.__setattr__(self, "_por_id", por_id)

    def __contains__(self, local_id: object) -> bool:
        return local_id in self._por_id

    @property
    def ids(self) -> tuple[str, ...]:
        """Os ids na ordem em que o grafo foi montado."""
        return tuple(self._por_id)

    def local(self, local_id: str) -> LocalNoGrafo:
        """O local pedido, ou `LocalDesconhecido` — que o router traduz em 404."""
        local = self._por_id.get(local_id)
        if local is None:
            raise LocalDesconhecido(
                "Este local nao existe no mapa de Kanto.",
                detalhes={"local_id": local_id},
            )
        return local


def montar_grafo(locais: Iterable[LocalNoGrafo]) -> GrafoDeLocais:
    """Monta e valida o grafo a partir dos locais lidos pelo servico."""
    return GrafoDeLocais(tuple(locais))


# --- Saida -----------------------------------------------------------------


class EstadoDoLocal(StrEnum):
    """Os tres estados da regra 2 da spec 005, nos nomes que a API devolve."""

    VISITADO = "VISITADO"
    ALCANCAVEL = "ALCANCAVEL"
    FORA_DE_ALCANCE = "FORA_DE_ALCANCE"


@dataclass(frozen=True, slots=True)
class RotaAteLocal:
    """A ida mais curta ate um destino, a partir do conjunto de visitados.

    `caminho` inclui a origem e o destino. `custo_viagem_minutos` soma o custo
    de travessia de cada local do caminho **exceto a origem**, que e onde o
    treinador ja esta — e por isso um destino ja visitado tem viagem zero
    (regra 4 da spec 005: revisitar e permitido).
    """

    destino_id: str
    origem_id: str
    caminho: tuple[str, ...]
    custo_viagem_minutos: int

    @property
    def proximo_local_id(self) -> str | None:
        """O primeiro local do caminho depois da origem, se houver."""
        passo = self.caminho[1:2]
        return passo[0] if passo else None


@dataclass(frozen=True, slots=True)
class LocalNoMapa:
    """A linha do mapa para um local, como a tela precisa dela.

    `origem_id`, `caminho`, `custo_viagem_minutos` e `duracao_estimada_minutos`
    vem nulos quando o local esta fora de alcance; `proximo_passo_id` vem nulo
    quando ele ja esta ao alcance, porque nao falta nada.
    """

    id: str
    estado: EstadoDoLocal
    origem_id: str | None = None
    caminho: tuple[str, ...] = ()
    custo_viagem_minutos: int | None = None
    duracao_estimada_minutos: int | None = None
    proximo_passo_id: str | None = None


# --- Alcance (regras 2 a 4 da spec 005) -------------------------------------


def _visitados_conhecidos(grafo: GrafoDeLocais, visitados: Collection[str]) -> tuple[str, ...]:
    """Os visitados que existem no grafo, ordenados por id.

    Um visitado que nao esta no grafo e ignorado em vez de recusado: o mapa e
    leitura, e um local desbloqueado que saiu do seed nao pode derrubar a tela
    inteira. A ordenacao por id e o que torna o resultado independente da ordem
    de iteracao do conjunto recebido (Artigo III).
    """
    return tuple(sorted({local_id for local_id in visitados if local_id in grafo}))


def alcancaveis(grafo: GrafoDeLocais, visitados: Collection[str]) -> tuple[str, ...]:
    """Os vizinhos dos locais visitados que ainda nao foram visitados.

    Regra 3 da spec 005. Sai ordenado por id, e nao na ordem do grafo nem na do
    conjunto recebido, para que a saida nao dependa de como a entrada chegou.

    Com `visitados` vazio — estado que nao acontece em jogo, porque Pallet Town
    nasce visitada — a resposta e vazia, e nao um erro: nada e vizinho de nada.
    """
    conhecidos = _visitados_conhecidos(grafo, visitados)
    vizinhanca = {
        vizinho_id for local_id in conhecidos for vizinho_id in grafo.local(local_id).vizinhos
    }
    return tuple(sorted(vizinhanca.difference(conhecidos)))


def estado_de(
    local_id: str,
    visitados: Collection[str],
    alcancaveis_agora: Collection[str],
) -> EstadoDoLocal:
    """Classifica um local nos tres estados da regra 2.

    Recebe o alcance ja calculado em vez de recalcula-lo: a tela do mapa
    classifica os dez locais de uma vez, e dez varreduras do grafo para a mesma
    resposta seriam dez vezes o mesmo trabalho. `visitado` vence `alcancavel`
    quando o local e as duas coisas — um local visitado vizinho de outro
    visitado continua visitado.
    """
    if local_id in visitados:
        return EstadoDoLocal.VISITADO
    if local_id in alcancaveis_agora:
        return EstadoDoLocal.ALCANCAVEL
    return EstadoDoLocal.FORA_DE_ALCANCE


# --- Rotas otimas (Dijkstra multi-origem) -----------------------------------


def rotas_otimas(grafo: GrafoDeLocais, visitados: Collection[str]) -> dict[str, RotaAteLocal]:
    """A ida mais barata ate cada local alcancavel, numa unica busca.

    Dijkstra com todos os visitados na fila inicial a custo zero. Locais sem
    caminho a partir dos visitados — um no isolado, ou o mapa inteiro quando
    nao ha visitado nenhum — simplesmente nao aparecem no resultado, em vez de
    aparecerem com custo infinito: ausencia e o que "fora de alcance"
    significa, e quem le nao precisa comparar com sentinela.

    O dicionario sai na ordem em que os destinos foram resolvidos, ou seja, do
    mais perto para o mais longe — que e a ordem util para a tela.
    """
    melhores: dict[str, RotaAteLocal] = {}
    fila: list[tuple[int, tuple[str, ...]]] = []
    for origem_id in _visitados_conhecidos(grafo, visitados):
        heappush(fila, (0, (origem_id,)))

    while fila:
        custo, caminho = heappop(fila)
        destino_id = caminho[-1]
        if destino_id in melhores:
            continue
        melhores[destino_id] = RotaAteLocal(
            destino_id=destino_id,
            origem_id=caminho[0],
            caminho=caminho,
            custo_viagem_minutos=custo,
        )
        for vizinho_id in grafo.local(destino_id).vizinhos:
            if vizinho_id in melhores:
                continue
            vizinho = grafo.local(vizinho_id)
            heappush(fila, (custo + vizinho.custo_travessia_minutos, (*caminho, vizinho_id)))

    return melhores


def rota_ate(
    grafo: GrafoDeLocais, visitados: Collection[str], local_id: str
) -> RotaAteLocal | None:
    """A rota ate um destino so, para quem nao precisa do mapa inteiro.

    Um id inexistente e recusado antes da busca, e nao devolvido como "sem
    rota": nao existir e nao ter caminho sao respostas diferentes, e a primeira
    e um 404.
    """
    grafo.local(local_id)
    return rotas_otimas(grafo, visitados).get(local_id)


def proximo_passo(grafo: GrafoDeLocais, visitados: Collection[str], local_id: str) -> str | None:
    """O que visitar primeiro para abrir um local fora de alcance (regra 8).

    E o primeiro no do caminho mais curto a partir dos visitados, e nao a lista
    inteira ate o destino: a resposta util para o professor e "visite Route 1",
    nao "visite Route 1, depois Viridian City, depois Route 2".

    Devolve `None` quando nao falta nada — local ja visitado ou ja alcancavel —
    e tambem quando nao ha caminho algum, caso de um no isolado no grafo ou de
    um mapa sem nenhum local visitado. Um id inexistente, ao contrario, e
    recusado: nao existir nao e o mesmo que nao faltar nada.
    """
    grafo.local(local_id)
    estado = estado_de(local_id, visitados, alcancaveis(grafo, visitados))
    if estado is not EstadoDoLocal.FORA_DE_ALCANCE:
        return None
    rota = rotas_otimas(grafo, visitados).get(local_id)
    return rota.proximo_local_id if rota is not None else None


def exigir_destino_alcancavel(
    grafo: GrafoDeLocais, visitados: Collection[str], destino_id: str
) -> RotaAteLocal:
    """Invariante 6 do SDD 3.3, imposto no dominio (Artigo VI).

    O destino de uma expedicao precisa ser um local visitado ou vizinho de um
    visitado. Devolve a rota, porque quem despacha a expedicao precisa logo em
    seguida da origem e do custo da viagem — recusar sem devolve-la obrigaria a
    Fase 6 a repetir a busca.
    """
    grafo.local(destino_id)
    estado = estado_de(destino_id, visitados, alcancaveis(grafo, visitados))
    if estado is EstadoDoLocal.FORA_DE_ALCANCE:
        passo = proximo_passo(grafo, visitados, destino_id)
        falta = f" Visite {passo} antes." if passo else ""
        raise DestinoForaDeAlcance(
            f"Este local ainda esta fora de alcance do laboratorio.{falta}",
            detalhes={"local_id": destino_id, "proximo_passo_id": passo},
        )
    return rotas_otimas(grafo, visitados)[destino_id]


# --- Duracao estimada (SDD 4.4) ---------------------------------------------


def _fracao(valor: float) -> Fraction:
    """`Fraction(str(0.02))` da 1/50; `Fraction(0.02)` daria a aproximacao binaria.

    Mesma decisao de `experience.py` e `power.py`: a conta corre exata para que
    a calibragem da Fase 8 nao mude um arredondamento por efeito colateral.
    """
    return Fraction(str(valor))


def _desconto_do_treinador(nivel_treinador: int | None) -> Fraction:
    """1 - min(nivel * REDUCAO_POR_NIVEL_TREINADOR, REDUCAO_MAXIMA_TREINADOR).

    Sem treinador informado nao ha desconto: e a estimativa base que o mapa
    mostra antes de o professor escolher quem mandar.
    """
    if nivel_treinador is None:
        return Fraction(1)
    exigir_nivel_de_treinador(nivel_treinador)
    reducao = min(
        nivel_treinador * _fracao(balance.REDUCAO_POR_NIVEL_TREINADOR),
        _fracao(balance.REDUCAO_MAXIMA_TREINADOR),
    )
    return 1 - reducao


def _desconto_dos_itens(bonus_itens: float) -> Fraction:
    """1 - bonus_itens, com o bonus limitado a BONUS_ITENS_MAXIMO.

    O teto e corte, nao recusa: a carga que o professor montou e valida, e o
    que o SDD limita e quanto dela acelera a expedicao. Bonus negativo, ao
    contrario, e chamada errada — ele atrasaria a expedicao, e nenhum item faz
    isso.
    """
    if bonus_itens < 0:
        raise ParametroDeDuracaoInvalido(f"Bonus de itens negativo: {bonus_itens}.")
    return 1 - min(_fracao(bonus_itens), _fracao(balance.BONUS_ITENS_MAXIMO))


def duracao_estimada(
    *,
    custo_viagem_minutos: int,
    encontros_base: int,
    nivel_treinador: int | None = None,
    bonus_itens: float = 0.0,
    escala: float = 1.0,
) -> int:
    """A duracao da ida, em minutos, pela formula da secao 4.4 do SDD.

        duracao = (tempo_viagem + encontros_base * MINUTOS_POR_ENCONTRO)
                * (1 - min(nivel * REDUCAO_POR_NIVEL_TREINADOR, REDUCAO_MAXIMA))
                * (1 - bonus_itens)
                * escala

    Conferencia contra o exemplo do proprio SDD: Mt. Moon partindo de Pallet
    Town tem viagem de 34 minutos e 7 encontros base, logo 34 + 21 = 55
    minutos; partindo de Route 3, 8 + 21 = 29.

    `escala` e o `EXPEDITION_TIME_SCALE` do ADR-004, que e ambiente e nao
    calibragem: por isso chega como parametro e nao mora em `balance.py`. Ela
    **divide**, como a formula do SDD escreve, entao um valor acima de 1
    acelera e um valor abaixo de 1 alonga.

    Os argumentos sao todos nomeados de proposito: sao cinco numeros, e uma
    troca de posicao entre eles produziria uma duracao plausivel e errada.
    """
    if custo_viagem_minutos < 0:
        raise ParametroDeDuracaoInvalido(f"Custo de viagem negativo: {custo_viagem_minutos}.")
    if encontros_base < 0:
        raise ParametroDeDuracaoInvalido(f"Numero de encontros negativo: {encontros_base}.")
    if escala <= 0:
        raise ParametroDeDuracaoInvalido(f"Escala de tempo invalida: {escala}.")

    tempo_exploracao = encontros_base * balance.MINUTOS_POR_ENCONTRO
    bruta = Fraction(custo_viagem_minutos + tempo_exploracao)
    # A escala MULTIPLICA: 0.01 encolhe vinte minutos para doze segundos, que e
    # o que o ADR-004 e o .env.example sempre descreveram. O SDD dizia "divide"
    # ate a Fase 5, e seguir o texto deixava a expedicao cem vezes mais longa
    # em desenvolvimento. O documento e que foi corrigido.
    ajustada = (
        bruta * _desconto_do_treinador(nivel_treinador) * _desconto_dos_itens(bonus_itens)
    ) * _fracao(escala)
    return max(balance.DURACAO_MINIMA_MINUTOS, round(ajustada))


def duracao_da_rota(
    grafo: GrafoDeLocais,
    rota: RotaAteLocal,
    *,
    nivel_treinador: int | None = None,
    bonus_itens: float = 0.0,
    escala: float = 1.0,
) -> int:
    """`duracao_estimada` para uma rota ja calculada, com os encontros do destino."""
    return duracao_estimada(
        custo_viagem_minutos=rota.custo_viagem_minutos,
        encontros_base=grafo.local(rota.destino_id).encontros_base,
        nivel_treinador=nivel_treinador,
        bonus_itens=bonus_itens,
        escala=escala,
    )


# --- O mapa inteiro ---------------------------------------------------------


def visao_do_mapa(
    grafo: GrafoDeLocais,
    visitados: Collection[str],
    *,
    nivel_treinador: int | None = None,
    bonus_itens: float = 0.0,
    escala: float = 1.0,
) -> tuple[LocalNoMapa, ...]:
    """Os dez locais com estado, origem, duracao e o que falta, de uma vez so.

    Existe para que `GET /map` e `GET /map/{id}` leiam a mesma resposta da
    mesma funcao: estado divergente entre a lista e o detalhe seria um bug
    invisivel do lado do servidor e visivel do lado do professor.

    Sai ordenada por custo de viagem e, em caso de empate, por id — a ordem
    util e "o que esta mais perto de mim agora", e ela muda conforme o
    professor progride (regra 1: os dez aparecem sempre, inclusive os fora de
    alcance, que vao para o fim).
    """
    rotas = rotas_otimas(grafo, visitados)
    ao_alcance = alcancaveis(grafo, visitados)

    linhas: list[LocalNoMapa] = []
    for local_id in _ordem_por_distancia(grafo, rotas):
        estado = estado_de(local_id, visitados, ao_alcance)
        rota = rotas.get(local_id)
        if estado is EstadoDoLocal.FORA_DE_ALCANCE or rota is None:
            linhas.append(
                LocalNoMapa(
                    id=local_id,
                    estado=estado,
                    proximo_passo_id=rota.proximo_local_id if rota is not None else None,
                )
            )
            continue
        linhas.append(
            LocalNoMapa(
                id=local_id,
                estado=estado,
                origem_id=rota.origem_id,
                caminho=rota.caminho,
                custo_viagem_minutos=rota.custo_viagem_minutos,
                duracao_estimada_minutos=duracao_da_rota(
                    grafo,
                    rota,
                    nivel_treinador=nivel_treinador,
                    bonus_itens=bonus_itens,
                    escala=escala,
                ),
            )
        )

    return tuple(linhas)


def _ordem_por_distancia(grafo: GrafoDeLocais, rotas: dict[str, RotaAteLocal]) -> tuple[str, ...]:
    """Os ids do mais perto ao mais longe, com os sem caminho no fim.

    A distancia usada e a do caminho, inclusive para quem esta fora de alcance:
    a spec pede os dez locais "em ordem de proximidade do laboratorio", e
    Cerulean City nao e o terceiro lugar do mapa so porque comeca com C.

    O grupo vem antes do custo na chave porque "sem caminho" nao e um custo
    grande: um sentinela numerico teria de ser maior que qualquer viagem
    possivel, e esse "qualquer" muda a cada local novo no seed. O id entra como
    ultimo criterio para que dois locais equidistantes saiam sempre na mesma
    ordem (Artigo III).
    """

    def chave(local_id: str) -> tuple[int, int, str]:
        rota = rotas.get(local_id)
        if rota is None:
            return (1, 0, local_id)
        return (0, rota.custo_viagem_minutos, local_id)

    return tuple(sorted(grafo.ids, key=chave))
