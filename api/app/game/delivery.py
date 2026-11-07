"""Central de Entregas: geracao do pedido, prazo da oferta e recompensa (SDD 4.9).

Este modulo responde tres perguntas, e so elas: **o que a Central pede hoje**,
**ate quando o pedido vale** e **quanto ele paga**. Quem persiste, trava e
compromete Pokemon e `services/`; aqui nao ha estado.

Cinco decisoes de desenho valem o comentario.

**A escala de raridade anda ao contrario da intuicao.** `taxa_captura` vai de 3
(Mewtwo) a 255 (Caterpie), com mediana em 75: taxa ALTA e especie COMUM. Por
isso a banda do laboratorio e um PISO que DESCE conforme o nivel sobe — nivel 1
alcanca so o topo da escala, e cada nivel estende a banda para baixo, na
direcao do raro. Escrever a desigualdade ao contrario faz o laboratorio recem
criado encomendar Mewtwo, e e o erro provavel desta regra: a tabela de
`test_game_delivery.py` existe para pega-lo.

**A Pokedex nao participa.** Sortear do que o professor ja viu faria da Central
um laco fechado: ela so pediria o que ele ja conhece, e um sistema que devia
empurra-lo para fora do mapa conhecido viraria eco do que ele ja fez. Um pedido
de Clefairy para quem nunca pisou em Mt. Moon e exatamente o ponto. A banda de
raridade faz o trabalho sozinha — o que e raro e, por construcao, o que ele
provavelmente ainda nao viu —, e um sistema com uma alavanca so e mais facil de
calibrar na Fase 9 do que um com duas.

**Alcancavel e a mesma nocao de `mapa.exigir_destino_alcancavel`**: local
visitado, ou vizinho de visitado. Reaproveitada, nao reescrita. Sem esse filtro
o gerador pede Dragonite a quem esta em Pallet Town, e isso nao e objetivo, e
ruido — o pedido nomeia algo que o professor nao tem como obter.

**`EXPIRADA` e derivado, nunca gravado.** A coluna `status` continua
`DISPONIVEL` e a expiracao se calcula na leitura, por uma funcao unica. E o
terceiro uso do padrao, depois de `expedition.estado_observado` e de
`stats.hp_recuperado`, e pelo mesmo motivo do ADR-004: gravar a transicao
exigiria um job varrendo o banco, e nao ha um. Dois lugares derivando diferente
e um bug que aparece como pedido aceitavel numa tela e vencido na outra.

**A escala de tempo MULTIPLICA.** `EXPEDITION_TIME_SCALE` e ambiente e nao
calibragem (ADR-004): nao mora em `balance.py` e nao e lida aqui dentro — chega
como argumento, como manda o Artigo I. Vale tanto para a duracao da viagem
quanto para o prazo da oferta.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from fractions import Fraction
from typing import Any, ClassVar

from app.game import balance, mapa
from app.game.aleatoriedade import GeradorAleatorio
from app.game.erros import ErroDeDominio, NivelInvalido, TaxaDeCapturaInvalida
from app.game.expedition import exigir_instante_com_fuso, tempo_restante
from app.game.experience import NIVEL_MINIMO
from app.game.laboratorio import NivelDeLaboratorioInvalido

# Texto do titulo do pedido. Nao e numero, mas mora aqui em cima pelo mesmo
# motivo que os numeros moram em balance.py: a frase que o professor le tem um
# dono so, e nao se escreve duas vezes (Artigo X).
TITULO_DO_PEDIDO = "Encomenda para {destino}"

# Piso de qualquer prazo derivado da escala de tempo. Com uma escala muito
# pequena a conta chega abaixo de um segundo, e uma oferta que nasce vencida
# nunca foi oferta. Nao e calibragem: e o grao do relogio.
_PRAZO_MINIMO = timedelta(seconds=1)


# --- Erros (Artigo VI) ------------------------------------------------------


class ErroDeEntrega(ErroDeDominio):
    """Raiz das recusas da Central de Entregas.

    O `codigo` e o mesmo do contrato de API, declarado uma vez aqui para que o
    router nao mantenha a propria tabela de traducao — mesmo arranjo de
    `team.py` e de `mapa.py`.
    """

    codigo: ClassVar[str] = "ENTREGA_INVALIDA"

    def __init__(self, mensagem: str, *, detalhes: dict[str, Any] | None = None) -> None:
        self.detalhes = detalhes or {}
        super().__init__(mensagem)


class CatalogoDeEntregaInvalido(ErroDeEntrega):
    """As especies ou as cidades recebidas nao descrevem um sorteio possivel."""

    codigo: ClassVar[str] = "CATALOGO_DE_ENTREGA_INVALIDO"


class SemEspecieCandidata(ErroDeEntrega):
    """Nem com a banda aberta ate o fundo ha especie em local alcancavel."""

    codigo: ClassVar[str] = "SEM_ESPECIE_CANDIDATA"


class SemCidadeDeDestino(ErroDeEntrega):
    """Invariante 16: o destino e sempre uma cidade desbloqueada, e nao ha nenhuma."""

    codigo: ClassVar[str] = "SEM_CIDADE_DE_DESTINO"


class StatusDeEntregaDesconhecido(ErroDeEntrega):
    """A coluna `status` guarda um valor que o dominio nao reconhece."""

    codigo: ClassVar[str] = "STATUS_DE_ENTREGA_DESCONHECIDO"


class PrazoDeEntregaAusente(ErroDeEntrega):
    """Falta o instante que a derivacao do estado exige (regra 16 da spec 008)."""

    codigo: ClassVar[str] = "PRAZO_DE_ENTREGA_AUSENTE"


class ParametroDeEntregaInvalido(ErroDeEntrega):
    """Um dos numeros que alimentam duracao ou recompensa nao e utilizavel."""

    codigo: ClassVar[str] = "PARAMETRO_DE_ENTREGA_INVALIDO"


class PokemonNaoAtendeAoPedido(ErroDeEntrega):
    """Regra 21 da spec 008: o conjunto escolhido nao bate com o pedido."""

    codigo: ClassVar[str] = "POKEMON_NAO_ATENDE_AO_PEDIDO"


# --- Entrada ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EspecieParaEntrega:
    """O minimo que o gerador precisa saber de uma especie.

    `locais_ids` sao os locais em que a especie aparece em `LocalEncontro`
    (SDD 3.1) — e o que torna o pedido alcancavel ou ruido. Nenhum modelo ORM
    atravessa esta fronteira: o Artigo I nao sobreviveria a um
    `PokemonEspecie` do SQLAlchemy aqui dentro, e quem le o banco e
    `services/`.
    """

    id: int
    nome: str
    taxa_captura: int
    locais_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CidadeDeDestino:
    """Uma cidade ja desbloqueada, candidata a destino (invariante 16)."""

    id: str
    nome: str


@dataclass(frozen=True, slots=True)
class PokemonEntregue:
    """O que a conclusao da entrega tira do laboratorio, para efeito de pagamento."""

    especie_nome: str
    nivel: int


# --- Saida ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RequisitoDoPedido:
    """Uma linha do pedido: tantos de tal especie."""

    especie_id: int
    especie_nome: str
    quantidade: int


@dataclass(frozen=True, slots=True)
class PedidoDeEntrega:
    """Um pedido recem-sorteado, antes de virar linha no banco.

    Nao tem `id`, `expira_em` nem `status`: esses nascem na gravacao. O que o
    dominio produz e o conteudo do pedido, e nada mais.
    """

    titulo: str
    local_destino_id: str
    local_destino_nome: str
    requisitos: tuple[RequisitoDoPedido, ...]

    @property
    def total_pedido(self) -> int:
        """Quantos Pokemon o pedido inteiro leva embora."""
        return sum(requisito.quantidade for requisito in self.requisitos)


@dataclass(frozen=True, slots=True)
class RecompensaDeEntrega:
    """O que a conclusao credita (SDD 4.9)."""

    moedas: int
    exp_laboratorio: int
    exp_treinador: int
    total_entregue: int


class StatusEntrega(StrEnum):
    """O que a coluna `status` grava.

    `EXPIRADA` nao esta aqui de proposito: ela nao e fato gravado, e sim
    leitura do relogio contra `expira_em`.
    """

    DISPONIVEL = "DISPONIVEL"
    EM_CURSO = "EM_CURSO"
    CONCLUIDA = "CONCLUIDA"
    DESCARTADA = "DESCARTADA"

    @property
    def aceita_prazo_da_oferta(self) -> bool:
        """Se o `expira_em` ainda decide alguma coisa.

        So decide enquanto o pedido e oferta. Aceito, ele virou viagem com
        `eta` proprio e nao expira mais — os Pokemon ja estao comprometidos e o
        treinador ja saiu (SDD 4.9).
        """
        return self is StatusEntrega.DISPONIVEL


class EstadoObservadoEntrega(StrEnum):
    """O estado que o professor ve: o gravado, corrigido pelo relogio.

    Tem um valor a mais que `StatusEntrega`, e so um: `EXPIRADA`, a oferta que
    venceu sem aceite.
    """

    DISPONIVEL = "DISPONIVEL"
    EXPIRADA = "EXPIRADA"
    EM_CURSO = "EM_CURSO"
    CONCLUIDA = "CONCLUIDA"
    DESCARTADA = "DESCARTADA"

    @property
    def aceitavel(self) -> bool:
        """Se o pedido ainda pode ser aceito (criterio 20 da spec 008)."""
        return self is EstadoObservadoEntrega.DISPONIVEL

    @property
    def ocupa_vaga_na_lista(self) -> bool:
        """Se este pedido conta contra `ENTREGAS_DISPONIVEIS`.

        So a oferta valida ocupa vaga. Vencida, aceita, concluida ou
        descartada, ela saiu de circulacao e abriu lugar para outra — e repor
        esse lugar nao consome o intervalo de regeracao (invariante 23).
        """
        return self is EstadoObservadoEntrega.DISPONIVEL


# --- Banda de raridade (SDD 4.9) --------------------------------------------


def _exigir_nivel_de_laboratorio(nivel: int) -> None:
    if nivel < 1:
        raise NivelDeLaboratorioInvalido(f"Nivel de laboratorio invalido: {nivel}.")


def _exigir_taxa_valida(especie: EspecieParaEntrega) -> None:
    if (
        especie.taxa_captura < balance.TAXA_CAPTURA_MINIMA
        or especie.taxa_captura > balance.TAXA_CAPTURA_MAXIMA
    ):
        raise TaxaDeCapturaInvalida(
            f"A taxa de captura de {especie.nome} esta fora da faixa do seed, de "
            f"{balance.TAXA_CAPTURA_MINIMA} a {balance.TAXA_CAPTURA_MAXIMA}: "
            f"{especie.taxa_captura}."
        )


def piso_de_raridade(nivel_laboratorio: int) -> int:
    """A menor `taxa_captura` que o laboratorio alcanca neste nivel.

    A escala anda ao contrario da intuicao: taxa ALTA e especie COMUM. Logo
    este piso DESCE conforme o nivel sobe, e a banda e sempre
    `[piso, TAXA_CAPTURA_MAXIMA]`.

        piso(1) = TAXA_CAPTURA_MAXIMA                     -> so o topo, comum
        piso(NIVEL_LABORATORIO_BANDA_TOTAL) = TAXA_CAPTURA_MINIMA  -> tudo

    Entre os dois extremos a descida e linear, em aritmetica inteira: o degrau
    e `(255 - 3) // (NIVEL_TOTAL - 1)` aplicado sobre os niveis ja vencidos. A
    divisao inteira trunca a DESCIDA, nao o piso, de modo que o erro de
    arredondamento sempre deixa a banda um pouco mais conservadora — mais perto
    do comum — em vez de abrir o raro antes da hora.

    Com os numeros atuais: nivel 1 so alcanca taxa 255 (Pidgey, Rattata,
    Caterpie), nivel 3 ja alcanca Pikachu e Psyduck (190), nivel 8 passa da
    mediana da escala (75) e nivel 10 alcanca Mewtwo.
    """
    _exigir_nivel_de_laboratorio(nivel_laboratorio)
    niveis_vencidos = nivel_laboratorio - 1
    niveis_ate_abrir = balance.NIVEL_LABORATORIO_BANDA_TOTAL - 1
    if niveis_vencidos >= niveis_ate_abrir:
        return balance.TAXA_CAPTURA_MINIMA
    largura = balance.TAXA_CAPTURA_MAXIMA - balance.TAXA_CAPTURA_MINIMA
    return balance.TAXA_CAPTURA_MAXIMA - (niveis_vencidos * largura) // niveis_ate_abrir


def banda_de_raridade(nivel_laboratorio: int) -> tuple[int, int]:
    """A faixa fechada de `taxa_captura` que este nivel encomenda."""
    return piso_de_raridade(nivel_laboratorio), balance.TAXA_CAPTURA_MAXIMA


def locais_ao_alcance(grafo: mapa.GrafoDeLocais, visitados: Collection[str]) -> tuple[str, ...]:
    """Os locais de onde o professor pode trazer alguma coisa hoje.

    E a mesma nocao de `mapa.exigir_destino_alcancavel` — visitado, ou vizinho
    de visitado —, classificada pela mesma `mapa.estado_de` e nao por uma
    segunda regra escrita aqui. Sai ordenado por id, para que nada dependa da
    ordem de iteracao da colecao recebida (Artigo III).
    """
    alcancaveis_agora = mapa.alcancaveis(grafo, visitados)
    return tuple(
        sorted(
            local_id
            for local_id in grafo.ids
            if mapa.estado_de(local_id, visitados, alcancaveis_agora)
            is not mapa.EstadoDoLocal.FORA_DE_ALCANCE
        )
    )


def _ordenar_especies(especies: Iterable[EspecieParaEntrega]) -> tuple[EspecieParaEntrega, ...]:
    """Ordem canonica: `especie_id` crescente.

    A ordem e parte do resultado do sorteio, entao ela e imposta aqui e nao
    confiada a quem chama. Uma consulta que mudasse o `ORDER BY` moveria o
    pedido de toda semente ja gravada, e o Artigo III viraria promessa.
    """
    ordenadas = tuple(sorted(especies, key=lambda especie: especie.id))
    vistos: set[int] = set()
    for especie in ordenadas:
        _exigir_taxa_valida(especie)
        if especie.id in vistos:
            raise CatalogoDeEntregaInvalido(
                f"A especie {especie.id} aparece duas vezes no catalogo de entregas.",
                detalhes={"especie_id": especie.id},
            )
        vistos.add(especie.id)
    return ordenadas


def candidatas_do_nivel(
    nivel_laboratorio: int,
    especies: Iterable[EspecieParaEntrega],
    locais_alcancaveis: Collection[str],
) -> tuple[EspecieParaEntrega, ...]:
    """As especies encomendaveis hoje, em ordem canonica de `especie_id`.

        candidatas = especies dentro da banda do nivel
                   INTERSECAO especies que vivem em algum local alcancavel

    A Pokedex **nao** entra: ver o cabecalho do modulo.

    **Interseccao vazia tem resposta deliberada.** Ela e possivel — um seed
    novo, um mapa inicial mais pobre, ou uma calibragem que estreite demais a
    banda —, e deixar a excecao vazar para a tela transformaria uma lista vazia
    num erro. A saida e ALARGAR A BANDA, e o alargamento e deterministico: o
    piso desce pelo mesmo `piso_de_raridade`, um nivel de cada vez, ate achar
    candidata ou ate a banda estar aberta ate o fundo da escala. Nao ha sorteio
    nenhum no alargamento, entao a mesma entrada devolve sempre o mesmo
    conjunto.

    So quando nem a banda inteira acha candidata e que o dominio levanta: ai
    nao e banda estreita, e laboratorio sem nenhum local alcancavel com
    encontro — estado que nao existe em jogo, porque Pallet Town nasce
    visitada.
    """
    _exigir_nivel_de_laboratorio(nivel_laboratorio)
    ordenadas = _ordenar_especies(especies)
    alcance = set(locais_alcancaveis)

    nivel = nivel_laboratorio
    while True:
        piso = piso_de_raridade(nivel)
        candidatas = tuple(
            especie
            for especie in ordenadas
            if especie.taxa_captura >= piso
            and any(local_id in alcance for local_id in especie.locais_ids)
        )
        if candidatas:
            return candidatas
        if piso <= balance.TAXA_CAPTURA_MINIMA:
            raise SemEspecieCandidata(
                "Nenhuma especie do catalogo vive em local alcancavel por este "
                "laboratorio, nem com a banda de raridade aberta ate o fundo.",
                detalhes={"nivel_laboratorio": nivel_laboratorio},
            )
        nivel += 1


def teto_de_quantidade(taxa_captura: int) -> int:
    """Quantos exemplares da especie o pedido pode pedir, no maximo.

    `max(1, min(QUANTIDADE_MAXIMA_POR_ESPECIE, taxa // DIVISOR))` — a questao
    22 do SDD. Taxa alta e especie comum, entao o teto acompanha a taxa: 255 da
    tres, 190 da dois, 120 ou menos da um. Sem isso o pedido raro nasceria
    morto, pedindo tres Dragonite, e so queimaria um lugar da lista.
    """
    por_raridade = taxa_captura // balance.DIVISOR_QUANTIDADE_POR_CAPTURA
    return max(1, min(balance.QUANTIDADE_MAXIMA_POR_ESPECIE, por_raridade))


# --- Geracao do pedido (SDD 4.9) --------------------------------------------


def gerar_pedido(
    *,
    candidatas: Sequence[EspecieParaEntrega],
    cidades: Sequence[CidadeDeDestino],
    gerador: GeradorAleatorio,
) -> PedidoDeEntrega:
    """Um pedido sorteado a partir das candidatas e das cidades desbloqueadas.

    **A ordem das rolagens e contrato** (Artigo III), e esta e ela:

        1. destino          — indice uniforme sobre `cidades`
        2. quantas especies — 1 a min(ESPECIES_MAXIMAS_POR_ENTREGA, candidatas)
        3. por especie, em sequencia:
             a. indice uniforme sobre as candidatas ainda nao escolhidas
             b. quantidade, 1 a `teto_de_quantidade` da especie sorteada

    Trocar a ordem, ou pular uma rolagem quando so ha uma opcao, muda o
    resultado de toda semente ja gravada.

    **A especie e sorteada uniformemente dentro da banda**, e nao ponderada
    pela raridade. A banda ja e a unica alavanca de dificuldade do pedido (SDD
    4.9), e um segundo peso favorecendo o comum desfaria em silencio o que o
    nivel do laboratorio acabou de abrir.

    As candidatas chegam em ordem canonica — `especie_id` crescente, imposta
    por `candidatas_do_nivel` — e as cidades sao ordenadas por id aqui dentro,
    pelo mesmo motivo: ordem de iteracao que varia e determinismo quebrado.
    """
    if not candidatas:
        raise SemEspecieCandidata(
            "Nao ha especie candidata para montar o pedido.",
            detalhes={},
        )
    if not cidades:
        raise SemCidadeDeDestino(
            "Nenhuma cidade desbloqueada para receber a encomenda.",
            detalhes={},
        )

    destinos = tuple(sorted(cidades, key=lambda cidade: cidade.id))
    destino = destinos[gerador.randint(0, len(destinos) - 1)]

    maximo_de_especies = min(balance.ESPECIES_MAXIMAS_POR_ENTREGA, len(candidatas))
    quantas = gerador.randint(1, maximo_de_especies)

    restantes = list(candidatas)
    requisitos: list[RequisitoDoPedido] = []
    for _ in range(quantas):
        escolhida = restantes.pop(gerador.randint(0, len(restantes) - 1))
        quantidade = gerador.randint(1, teto_de_quantidade(escolhida.taxa_captura))
        requisitos.append(
            RequisitoDoPedido(
                especie_id=escolhida.id,
                especie_nome=escolhida.nome,
                quantidade=quantidade,
            )
        )

    return PedidoDeEntrega(
        titulo=TITULO_DO_PEDIDO.format(destino=destino.nome),
        local_destino_id=destino.id,
        local_destino_nome=destino.nome,
        # Os requisitos saem em ordem canonica de especie_id, e nao na ordem em
        # que o sorteio os tirou: duas listas com as mesmas linhas em ordens
        # diferentes seriam o mesmo pedido, e compara-las e trabalho da Fase 8.
        requisitos=tuple(sorted(requisitos, key=lambda requisito: requisito.especie_id)),
    )


def gerar_pedidos(
    quantidade: int,
    *,
    nivel_laboratorio: int,
    especies: Iterable[EspecieParaEntrega],
    grafo: mapa.GrafoDeLocais,
    visitados: Collection[str],
    cidades: Sequence[CidadeDeDestino],
    gerador: GeradorAleatorio,
) -> tuple[PedidoDeEntrega, ...]:
    """`quantidade` pedidos sorteados de uma vez, para preencher a lista.

    As candidatas sao calculadas UMA vez e reusadas nos `quantidade` sorteios:
    recalcular por pedido daria o mesmo conjunto e so custaria a varredura de
    novo.

    Pedidos repetidos sao possiveis e nao sao recusados. Duas encomendas de
    dois Pidgey para Viridian City sao um estado de jogo perfeitamente valido —
    e, num laboratorio nivel 1 cujo alcance tem duas especies, tentar evita-las
    estreitaria a lista a ponto de nao haver o que oferecer.
    """
    if quantidade < 0:
        raise ParametroDeEntregaInvalido(
            f"Quantidade de pedidos negativa: {quantidade}.",
            detalhes={"quantidade": quantidade},
        )
    if quantidade == 0:
        return ()
    candidatas = candidatas_do_nivel(
        nivel_laboratorio, especies, locais_ao_alcance(grafo, visitados)
    )
    return tuple(
        gerar_pedido(candidatas=candidatas, cidades=cidades, gerador=gerador)
        for _ in range(quantidade)
    )


# --- Prazo da oferta (SDD 4.9, terceiro uso do padrao do ADR-004) -----------


def _fracao(valor: float) -> Fraction:
    """`Fraction(str(0.02))` da 1/50; `Fraction(0.02)` daria a aproximacao binaria.

    Mesma decisao de `mapa.py`, `capture.py` e `experience.py`: a conta corre
    exata para que a calibragem da Fase 9 nao mude um arredondamento por efeito
    colateral.
    """
    return Fraction(str(valor))


def _exigir_escala_valida(escala: float) -> None:
    if escala <= 0:
        raise ParametroDeEntregaInvalido(
            f"Escala de tempo invalida: {escala}.",
            detalhes={"escala": escala},
        )


def _prazo_real(minutos_de_jogo: int, escala: float) -> timedelta:
    """Converte minutos de jogo em duracao real. A escala MULTIPLICA (ADR-004).

    `EXPEDITION_TIME_SCALE = 0.01` encolhe os 90 minutos da oferta para 54
    segundos, que e o que o ADR-004 e o `.env.example` sempre descreveram.
    Dividir deixaria a oferta cem vezes mais longa em desenvolvimento, que e o
    oposto do pretendido — o SDD dizia "divide" ate a Fase 5 e o documento e
    que foi corrigido.
    """
    _exigir_escala_valida(escala)
    bruto = timedelta(minutes=minutos_de_jogo) * escala
    return max(_PRAZO_MINIMO, bruto)


def duracao_da_oferta(escala: float = 1.0) -> timedelta:
    """Quanto tempo real um pedido recem-gerado fica aceitavel."""
    return _prazo_real(balance.VALIDADE_ENTREGA_MINUTOS, escala)


def expiracao_da_oferta(gerada_em: datetime, escala: float = 1.0) -> datetime:
    """O `expira_em` que o pedido grava ao nascer (regra 16 da spec 008).

    O instante de geracao chega como parametro: o Artigo I proibe o dominio de
    ler o relogio, e receber `agora` pronto e o que permite testar a virada do
    prazo sem congelar o relogio do processo.
    """
    exigir_instante_com_fuso(gerada_em, nome="gerada_em")
    return gerada_em + duracao_da_oferta(escala)


def status_de_entrega(valor: str | StatusEntrega) -> StatusEntrega:
    """Converte o texto gravado na coluna em status, recusando o que nao reconhece."""
    try:
        return StatusEntrega(valor)
    except ValueError:
        nomes = ", ".join(status.value for status in StatusEntrega)
        raise StatusDeEntregaDesconhecido(
            f"Status de entrega desconhecido: {valor!r}. Esperado um de: {nomes}.",
            detalhes={"status": str(valor)},
        ) from None


def estado_observado_entrega(
    status_gravado: str | StatusEntrega,
    expira_em: datetime | None,
    eta: datetime | None,
    agora: datetime,
) -> EstadoObservadoEntrega:
    """O estado real da entrega: o que esta gravado, corrigido pelo relogio.

    Esta e a **unica** funcao que deriva estado de entrega. Toda leitura passa
    por aqui — lista, detalhe, aceite e conclusao —, porque dois lugares
    comparando `expira_em` por conta propria acabariam discordando no limite, e
    o limite e justo onde o professor esta olhando: um pedido aceitavel numa
    tela e vencido na outra.

    Quatro bordas, decididas de proposito.

    **O prazo e da oferta, nao da missao.** Aceita, a entrega virou viagem com
    `eta` proprio e nao expira mais (SDD 4.9): `EM_CURSO`, `CONCLUIDA` e
    `DESCARTADA` ignoram `expira_em` inteiramente.

    **No empate o pedido JA venceu.** `agora` exatamente igual a `expira_em`
    devolve `EXPIRADA`, pela mesma razao de `expedition.estado_observado`:
    `expira_em` e o instante em que a oferta sai de circulacao, nao o ultimo
    instante em que ela vale. A alternativa deixaria a tela mostrando "0
    segundos restantes" ao lado de "disponivel", contradicao que o professor
    enxerga.

    **Oferta sem prazo e dado corrompido, nao oferta eterna.** A regra 16 diz
    que cada pedido nasce com prazo; uma linha `DISPONIVEL` com `expira_em`
    nulo nunca sairia da lista e empacaria a Central para sempre. O dominio
    levanta em vez de tratar como "nunca vence".

    **Nada e gravado aqui.** A coluna `status` continua `DISPONIVEL` depois de
    a funcao devolver `EXPIRADA` — a derivacao e leitura pura (criterio 19 da
    spec 008).
    """
    status = status_de_entrega(status_gravado)
    exigir_instante_com_fuso(agora, nome="agora")

    if not status.aceita_prazo_da_oferta:
        if status is StatusEntrega.EM_CURSO and eta is None:
            raise PrazoDeEntregaAusente(
                "Uma entrega em curso precisa de `eta` gravado.",
                detalhes={"parametro": "eta"},
            )
        if eta is not None:
            exigir_instante_com_fuso(eta, nome="eta")
        return EstadoObservadoEntrega(status.value)

    if expira_em is None:
        raise PrazoDeEntregaAusente(
            "Uma entrega disponivel precisa de `expira_em` gravado.",
            detalhes={"parametro": "expira_em"},
        )
    exigir_instante_com_fuso(expira_em, nome="expira_em")
    if agora >= expira_em:
        return EstadoObservadoEntrega.EXPIRADA
    return EstadoObservadoEntrega.DISPONIVEL


def segundos_para_expirar(expira_em: datetime, agora: datetime) -> int:
    """Quantos segundos a oferta ainda vale, nunca negativo.

    Delega a `expedition.tempo_restante`, que ja arredonda para cima e corre em
    `timedelta` inteiro: duas contagens regressivas com convencoes de
    arredondamento diferentes mostrariam "1s" numa tela e "0s" na outra para o
    mesmo instante. Zero segundos restantes acontece exatamente quando
    `estado_observado_entrega` devolve `EXPIRADA`, e nunca antes.
    """
    return tempo_restante(expira_em, agora)


# --- Regeracao da lista (invariantes 15 e 23) -------------------------------


def proxima_regeracao(ultimo_sorteio_em: datetime, escala: float = 1.0) -> datetime:
    """Quando o professor pode descartar a lista valida e sortear outra."""
    exigir_instante_com_fuso(ultimo_sorteio_em, nome="ultimo_sorteio_em")
    return ultimo_sorteio_em + _prazo_real(balance.INTERVALO_REGERAR_ENTREGAS_MINUTOS, escala)


def segundos_para_regerar(
    ultimo_sorteio_em: datetime | None,
    agora: datetime,
    escala: float = 1.0,
) -> int:
    """Quanto falta do intervalo de regeracao, em segundos.

    Sem sorteio anterior — laboratorio que nunca abriu a Central — nao ha
    espera: o primeiro sorteio nao e descarte de nada.
    """
    exigir_instante_com_fuso(agora, nome="agora")
    if ultimo_sorteio_em is None:
        return 0
    return tempo_restante(proxima_regeracao(ultimo_sorteio_em, escala), agora)


def vagas_para_repor(estados: Iterable[EstadoObservadoEntrega]) -> int:
    """Quantos pedidos faltam para a lista voltar a `ENTREGAS_DISPONIVEIS`.

    So a oferta valida ocupa lugar. Vencida, aceita, concluida ou descartada,
    ela saiu de circulacao — e repor esse lugar **nao** consome o intervalo
    (invariante 23): o intervalo existe contra rolar a sorte ate sair o pedido
    conveniente, e uma oferta que venceu sozinha nao e rolagem de sorte.
    """
    ocupadas = sum(1 for estado in estados if estado.ocupa_vaga_na_lista)
    return max(0, balance.ENTREGAS_DISPONIVEIS - ocupadas)


# --- Duracao da viagem (SDD 4.9) --------------------------------------------


def duracao_da_entrega(
    *,
    custo_viagem_minutos: int,
    nivel_treinador: int | None = None,
    escala: float = 1.0,
) -> int:
    """A duracao da entrega, em minutos, pela formula da secao 4.9 do SDD.

        duracao = tempo_viagem * MULTIPLICADOR_IDA_E_VOLTA
                * (1 - min(nivel * REDUCAO_POR_NIVEL_TREINADOR, REDUCAO_MAXIMA))
                * escala

    Nao ha exploracao nem encontro no caminho: entrega e so estrada, ida e
    volta. Por isso a formula nao e `mapa.duracao_estimada` com
    `encontros_base` zerado — o que muda nao e so o termo da exploracao, e o
    `MULTIPLICADOR_IDA_E_VOLTA`, que a expedicao nao tem.

    O desconto do treinador vem de `mapa.desconto_do_treinador` e nao de uma
    conta repetida aqui: a formula `1 - min(nivel * 0.02, 0.40)` e a mesma da
    expedicao, e duas copias divergiriam na primeira calibragem da Fase 9.

    O arredondamento acontece **uma vez**, no fim: dobrar a viagem antes de
    arredondar e dobrar um valor ja arredondado dao numeros diferentes, e o que
    o SDD escreve e a primeira.

    `escala` e o `EXPEDITION_TIME_SCALE` do ADR-004 e **multiplica**.
    """
    if custo_viagem_minutos < 0:
        raise ParametroDeEntregaInvalido(
            f"Custo de viagem negativo: {custo_viagem_minutos}.",
            detalhes={"custo_viagem_minutos": custo_viagem_minutos},
        )
    _exigir_escala_valida(escala)
    bruta = (
        Fraction(custo_viagem_minutos)
        * _fracao(balance.MULTIPLICADOR_IDA_E_VOLTA)
        * mapa.desconto_do_treinador(nivel_treinador)
        * _fracao(escala)
    )
    return max(balance.DURACAO_MINIMA_MINUTOS, round(bruta))


# --- Recompensa (SDD 4.9) ---------------------------------------------------


def _exigir_nivel_de_pokemon(entregue: PokemonEntregue) -> None:
    """Invariante 7 do SDD 3.3: nenhum Pokemon passa do nivel 100."""
    if entregue.nivel < NIVEL_MINIMO or entregue.nivel > balance.NIVEL_MAXIMO:
        raise NivelInvalido(
            f"Nivel {entregue.nivel} de {entregue.especie_nome} fora da faixa valida "
            f"de {NIVEL_MINIMO} a {balance.NIVEL_MAXIMO}."
        )


def moedas_por_pokemon(nivel: int, custo_viagem_minutos: int) -> Fraction:
    """`(MOEDA_BASE + nivel * MOEDA_POR_NIVEL) * (1 + tempo_viagem / 30)`.

    Devolve `Fraction` de proposito: e parcela de uma soma, e arredondar cada
    parcela faria o total depender de como os Pokemon foram agrupados. Quem
    arredonda e `recompensa_da_entrega`, uma vez so.

    Entregar longe paga mais e entregar nivel alto paga mais — e e decisao de
    verdade, porque esse Pokemon poderia estar num time. O bonus de distancia
    usa o tempo de viagem de IDA, nao o de ida e volta: o que paga e a
    distancia do destino, e dobra-la aqui dobraria tambem o efeito da
    calibragem de `MINUTOS_PARA_BONUS_DISTANCIA` sem ninguem perceber.
    """
    base = balance.MOEDA_BASE + nivel * balance.MOEDA_POR_NIVEL
    bonus = 1 + Fraction(custo_viagem_minutos, balance.MINUTOS_PARA_BONUS_DISTANCIA)
    return base * bonus


def recompensa_da_entrega(
    entregues: Sequence[PokemonEntregue],
    *,
    custo_viagem_minutos: int,
) -> RecompensaDeEntrega:
    """Moeda, experiencia do laboratorio e experiencia do treinador (SDD 4.9).

        moedas          = soma, por Pokemon, de moedas_por_pokemon
        exp_laboratorio = EXP_LAB_POR_ENTREGA * total_entregue
        exp_treinador   = EXP_TREINADOR_POR_ENTREGA

    A experiencia do laboratorio acompanha o tamanho da encomenda porque e o
    laboratorio que perde o acervo; a do treinador e por entrega, porque a
    viagem e uma so, leve ele um Pokemon ou tres.

    Uma entrega sem nenhum Pokemon e chamada errada, nao jogada possivel: o
    pedido pede ao menos uma especie e ao menos um exemplar (regra 10 da spec
    008).
    """
    if not entregues:
        raise ParametroDeEntregaInvalido(
            "Uma entrega concluida tem ao menos um Pokemon entregue.",
            detalhes={"total_entregue": 0},
        )
    if custo_viagem_minutos < 0:
        raise ParametroDeEntregaInvalido(
            f"Custo de viagem negativo: {custo_viagem_minutos}.",
            detalhes={"custo_viagem_minutos": custo_viagem_minutos},
        )
    for entregue in entregues:
        _exigir_nivel_de_pokemon(entregue)

    total = sum(
        (moedas_por_pokemon(entregue.nivel, custo_viagem_minutos) for entregue in entregues),
        Fraction(0),
    )
    return RecompensaDeEntrega(
        moedas=round(total),
        exp_laboratorio=balance.EXP_LAB_POR_ENTREGA * len(entregues),
        exp_treinador=balance.EXP_TREINADOR_POR_ENTREGA,
        total_entregue=len(entregues),
    )


# --- Conferencia do aceite (regra 21 da spec 008) ---------------------------


def exigir_pokemon_que_atendem(
    requisitos: Sequence[RequisitoDoPedido],
    especies_escolhidas: Sequence[int],
) -> None:
    """Invariante do aceite: o conjunto escolhido satisfaz EXATAMENTE o pedido.

    Nem a mais nem a menos, por especie. O professor escolhe QUAIS Pokemon
    manda — entre quatro Pidgey, qual par sai e decisao dele, e e decisao de
    verdade porque os niveis diferem e a recompensa paga por nivel —, mas o que
    ele escolhe tem de ser o que foi pedido: um Pidgey e um Rattata nao
    cumprem um pedido de dois Pidgey (criterio 24 da spec 008).

    A conferencia mora no dominio, e nao no router, porque e o Artigo VI: a
    validacao no router e conveniencia de interface, e a saida e definitiva.
    Recebe so os `especie_id`, na ordem em que o professor mandou — a ordem nao
    importa para a comparacao, e por isso a contagem e por especie.
    """
    pedido: dict[int, int] = {}
    for requisito in requisitos:
        pedido[requisito.especie_id] = pedido.get(requisito.especie_id, 0) + requisito.quantidade
    escolhido: dict[int, int] = {}
    for especie_id in especies_escolhidas:
        escolhido[especie_id] = escolhido.get(especie_id, 0) + 1

    if pedido == escolhido:
        return

    faltando = {
        especie_id: quantidade - escolhido.get(especie_id, 0)
        for especie_id, quantidade in pedido.items()
        if quantidade > escolhido.get(especie_id, 0)
    }
    sobrando = {
        especie_id: quantidade - pedido.get(especie_id, 0)
        for especie_id, quantidade in escolhido.items()
        if quantidade > pedido.get(especie_id, 0)
    }
    raise PokemonNaoAtendeAoPedido(
        "Os Pokemon escolhidos nao correspondem ao que a encomenda pede.",
        detalhes={"faltando": faltando, "sobrando": sobrando},
    )
