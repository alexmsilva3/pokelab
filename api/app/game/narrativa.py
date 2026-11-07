"""Os textos do relatorio de campo (tarefa 8 da spec 007).

O relatorio tem dois leitores. O professor le o **texto**: uma linha do tempo em
portugues, que conta quem enfrentou o que, de que nivel, e no que deu. A
interface le o **payload**: os numeros crus, para montar o resumo sem precisar
interpretar frase nenhuma. Este modulo cuida so da primeira metade.

Tres decisoes valem o comentario.

**A variacao e escolhida por indice, nunca sorteada.** Cada tipo de evento tem
duas ou tres frases, e a escolhida sai de `variacao % len(frases)`, onde
`variacao` e a ordem do evento na linha do tempo. Sortear a frase tambem
funcionaria, mas transformaria a redacao em mais uma rolagem dentro do contrato
de ordem do plano da spec 007 — e uma frase nova acrescentada na Fase 9
deslocaria todos os sorteios seguintes de toda semente ja gravada. Pelo indice,
o texto continua deterministico (Artigo III) e nao participa do sorteio.

**As frases informam antes de enfeitar.** Toda variante carrega os mesmos
fatos — nome, nivel, resultado —, muda so a forma. Uma variante que omitisse o
nivel faria o relatorio depender de qual sorteio caiu para ser util.

**Nome proprio fica em ingles** (Artigo X): `Caterpie`, `Mt. Moon`,
`Poke Ball`. O resto da frase e portugues.

O teto de `LIMITE_TEXTO_DO_EVENTO` e a largura da coluna que guarda o texto, e
e conferido aqui, na producao da frase: estourar o limite so na hora de gravar
transformaria um erro de redacao num erro de banco, longe de onde ele nasceu.
"""

from __future__ import annotations

from typing import Final

from app.game import balance
from app.game.erros import ErroDeDominio


class TextoLongoDemais(ErroDeDominio):
    """A frase de um evento passou do tamanho que a coluna do relatorio guarda."""


def _frase(frases: tuple[str, ...], variacao: int, **campos: object) -> str:
    """A variante escolhida pelo indice, ja preenchida e conferida.

    `variacao` e a ordem do evento na linha do tempo: eventos vizinhos do mesmo
    tipo saem com frases diferentes, e a mesma semente sempre produz o mesmo
    texto.
    """
    texto = frases[variacao % len(frases)].format(**campos)
    if len(texto) > balance.LIMITE_TEXTO_DO_EVENTO:
        raise TextoLongoDemais(
            f"O texto do evento tem {len(texto)} caracteres e o limite e "
            f"{balance.LIMITE_TEXTO_DO_EVENTO}: {texto[: balance.LIMITE_TEXTO_DO_EVENTO]}..."
        )
    return texto


def contagem(quantidade: int, singular: str, plural: str) -> str:
    """Concorda o numero com o substantivo: 1 vitoria, 4 vitorias.

    Existe porque "1 vitorias" num relatorio de campo denuncia que ninguem leu
    o texto depois de escrever o codigo.
    """
    return f"{quantidade} {singular if quantidade == 1 else plural}"


# --- Partida e retorno ------------------------------------------------------

_PARTIDA: Final[tuple[str, ...]] = (
    "{treinador} partiu de {origem} rumo a {destino}.",
    "{treinador} deixou {origem} com destino a {destino}.",
    "{treinador} saiu de {origem} em direcao a {destino}.",
)

_RETORNO_SUCESSO: Final[tuple[str, ...]] = (
    "{treinador} voltou ao laboratorio com {vitorias} em {encontros}.",
    "Expedicao encerrada: {treinador} trouxe {vitorias} de {encontros}.",
)

_RETORNO_FALHA: Final[tuple[str, ...]] = (
    "{treinador} voltou mais cedo ao laboratorio: "
    "{derrotas} seguidas sem nada para curar o time.{complemento}",
    "A expedicao foi interrompida depois de {derrotas} seguidas sem cura, "
    "e {treinador} voltou mais cedo.{complemento}",
)

_FUGA_COM_UMA_PERDA: Final[str] = " Na fuga, o unico Pokemon capturado ficou para tras."
_FUGA_COM_PERDAS: Final[str] = " Na fuga, os {perdidos} Pokemon capturados ficaram para tras."


def texto_de_partida(variacao: int, *, treinador: str, origem: str, destino: str) -> str:
    """Evento PARTIDA, sempre o primeiro da linha do tempo."""
    return _frase(_PARTIDA, variacao, treinador=treinador, origem=origem, destino=destino)


def texto_de_retorno(
    variacao: int,
    *,
    treinador: str,
    sucesso: bool,
    encontros: int,
    vitorias: int,
    derrotas_sem_cura: int,
    capturas_perdidas: int = 0,
) -> str:
    """Evento RETORNO, sempre o ultimo.

    A versao da falha conta as derrotas SEM CURA — as que encerraram a
    expedicao —, e nao o total de derrotas do dia: dizer "cinco derrotas" numa
    expedicao que acabou na terceira seguida sem Pocao explicaria errado a
    unica coisa que a ultima linha precisa explicar.

    Ela tambem nao cita vitorias de proposito. Elas aconteceram, estao na
    linha do tempo e a experiencia delas foi mantida (regra 16 da spec 007),
    mas o que o professor quer ler aqui e por que o treinador voltou antes da
    hora — e, se houve captura em campo, que ela se perdeu na fuga. Sem essa
    frase, o relatorio mostraria um evento `CAPTURA` e um resumo sem nenhuma
    captura, e o professor leria isso como defeito.
    """
    if sucesso:
        return _frase(
            _RETORNO_SUCESSO,
            variacao,
            treinador=treinador,
            vitorias=contagem(vitorias, "vitoria", "vitorias"),
            encontros=contagem(encontros, "encontro", "encontros"),
        )
    complemento = ""
    if capturas_perdidas == 1:
        complemento = _FUGA_COM_UMA_PERDA
    elif capturas_perdidas > 1:
        complemento = _FUGA_COM_PERDAS.format(perdidos=capturas_perdidas)
    return _frase(
        _RETORNO_FALHA,
        variacao,
        treinador=treinador,
        derrotas=contagem(derrotas_sem_cura, "derrota", "derrotas"),
        complemento=complemento,
    )


# --- Encontro ---------------------------------------------------------------

_BATALHA: Final[tuple[str, ...]] = (
    "{lider} enfrentou {especie} (nivel {nivel}) e venceu.",
    "{especie} (nivel {nivel}) apareceu no caminho e {lider} levou a melhor.",
    "{lider} cruzou com {especie} (nivel {nivel}) e saiu por cima.",
)

_CONTRATEMPO: Final[tuple[str, ...]] = (
    "{especie} (nivel {nivel}) foi demais para {lider}: "
    "o time perdeu {desgaste} pontos de vida.{complemento}",
    "{lider} nao deu conta de {especie} (nivel {nivel}) e "
    "o time voltou com {desgaste} pontos de vida a menos.{complemento}",
)

_CURA_EM_CAMPO: Final[str] = " O time usou {item} em campo."


def texto_de_batalha(variacao: int, *, lider: str, especie: str, nivel: int) -> str:
    """Evento BATALHA, emitido so na vitoria.

    `lider` e o primeiro Pokemon de pe do time — quem o professor imagina na
    frente da linha. A resolucao nao simula combate individual (ADR-003), entao
    o nome serve a narrativa e nao a mecanica: a chance saiu do poder do time
    inteiro, e ela esta no payload.
    """
    return _frase(_BATALHA, variacao, lider=lider, especie=especie, nivel=nivel)


def texto_de_contratempo(
    variacao: int,
    *,
    lider: str,
    especie: str,
    nivel: int,
    desgaste: int,
    item_usado: str | None = None,
) -> str:
    """Evento CONTRATEMPO, emitido so na derrota.

    A cura entra na mesma frase, e nao num evento proprio, porque
    `TipoDeEvento` e uniao fechada compartilhada com o frontend (plano da spec
    007) e `ITEM` significa item ACHADO. Dois significados no mesmo tipo
    fariam a tela desenhar o icone de achado para uma Pocao gasta.
    """
    complemento = "" if item_usado is None else _CURA_EM_CAMPO.format(item=item_usado)
    return _frase(
        _CONTRATEMPO,
        variacao,
        lider=lider,
        especie=especie,
        nivel=nivel,
        desgaste=desgaste,
        complemento=complemento,
    )


# --- Captura e Pokedex ------------------------------------------------------

_CAPTURA: Final[tuple[str, ...]] = (
    "{especie} (nivel {nivel}) entrou na {bola} e vem para o laboratorio.",
    "{bola} arremessada: {especie} (nivel {nivel}) foi capturado.",
)

_CAPTURA_FALHA: Final[tuple[str, ...]] = (
    "{especie} (nivel {nivel}) escapou da {bola} e sumiu no mato.",
    "A {bola} nao segurou {especie} (nivel {nivel}).",
)

_DESCOBERTA: Final[tuple[str, ...]] = (
    "Primeiro registro de {especie} na Pokedex, avistado em {local}.",
    "{especie} nunca tinha sido visto: a Pokedex anotou o avistamento em {local}.",
)


def texto_de_captura(variacao: int, *, especie: str, nivel: int, bola: str) -> str:
    """Evento CAPTURA."""
    return _frase(_CAPTURA, variacao, especie=especie, nivel=nivel, bola=bola)


def texto_de_captura_falha(variacao: int, *, especie: str, nivel: int, bola: str) -> str:
    """Evento CAPTURA_FALHA. A bola foi gasta do mesmo jeito (SDD 4.6)."""
    return _frase(_CAPTURA_FALHA, variacao, especie=especie, nivel=nivel, bola=bola)


def texto_de_descoberta(variacao: int, *, especie: str, local: str) -> str:
    """Evento DESCOBERTA, so na primeira vez que o laboratorio ve a especie."""
    return _frase(_DESCOBERTA, variacao, especie=especie, local=local)


_BAGAGEM_CHEIA: Final[tuple[str, ...]] = (
    "A bagagem de {treinador} ficou cheia com {capturados}: "
    "sem espaco, o que vier agora so vira registro na Pokedex.",
    "{treinador} nao tem mais onde por nada, com {capturados} na bagagem: "
    "daqui em diante o encontro rende so anotacao na Pokedex.",
)


def texto_de_bagagem_cheia(variacao: int, *, treinador: str, capturados: int) -> str:
    """Evento BAGAGEM_CHEIA: o momento em que a bagagem encheu.

    Existe porque o silencio enganava. Com a bagagem cheia no terceiro de
    cinco encontros, o relatorio mostrava duas batalhas vencidas sem nenhuma
    captura, e o professor nao tinha como distinguir "nao coube" de "a rolagem
    foi ruim" — duas situacoes que pedem decisoes opostas, levar um time menor
    ou levar mais bolas.

    A frase e escrita no estado, e nao no futuro: "ficou cheia" vale mesmo
    quando a captura que encheu foi a do ultimo encontro e nada mais chegou a
    acontecer. Ela tambem diz o que CONTINUA acontecendo — o registro na
    Pokedex segue (invariante 11) —, porque sem essa metade o professor leria
    o resto da expedicao como perdido.
    """
    return _frase(
        _BAGAGEM_CHEIA,
        variacao,
        treinador=treinador,
        capturados=contagem(capturados, "Pokemon capturado", "Pokemon capturados"),
    )


# --- Achado, nivel e evolucao -----------------------------------------------

_ITEM: Final[tuple[str, ...]] = (
    "O time achou {quantidade} de {item} pelo caminho.",
    "O time recolheu {quantidade} de {item} em {local}.",
)

_SUBIU_NIVEL: Final[tuple[str, ...]] = (
    "{pokemon} subiu do nivel {antes} para o nivel {depois}.",
    "{pokemon} ganhou experiencia suficiente e chegou ao nivel {depois}.",
)

_EVOLUCAO: Final[tuple[str, ...]] = (
    "{antes} evoluiu para {depois}.",
    "Uma luz tomou conta de {antes}, que evoluiu para {depois}.",
)


def texto_de_item(variacao: int, *, item: str, quantidade: int, local: str) -> str:
    """Evento ITEM: o que o treinador achou em campo depois de uma vitoria.

    O achado entra no estoque do laboratorio na resolucao, nunca na carga da
    expedicao em curso (regra 18 da spec 007) — por isso a frase fala em
    recolher, e nao em usar.
    """
    return _frase(
        _ITEM,
        variacao,
        item=item,
        quantidade=contagem(quantidade, "unidade", "unidades"),
        local=local,
    )


def texto_de_subiu_nivel(variacao: int, *, pokemon: str, antes: int, depois: int) -> str:
    """Evento SUBIU_NIVEL. Uma aplicacao de experiencia pode subir varios niveis."""
    return _frase(_SUBIU_NIVEL, variacao, pokemon=pokemon, antes=antes, depois=depois)


def texto_de_evolucao(variacao: int, *, antes: str, depois: str) -> str:
    """Evento EVOLUCAO. A cadeia encadeia e gera um evento por etapa (SDD 4.1)."""
    return _frase(_EVOLUCAO, variacao, antes=antes, depois=depois)
