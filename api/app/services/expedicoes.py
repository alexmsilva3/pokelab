"""Caso de uso do despacho de expedicoes (spec 006).

Este e o primeiro servico do PokeLab que le o relogio e sorteia uma semente
(Artigo I e III): nenhuma das duas coisas tem permissao de acontecer dentro
de `app.game`, e e aqui, na fronteira, que elas nascem e descem prontas para
o dominio.

**Concorrencia com dois alvos** (plan.md secao 5): um despacho pode disputar
o mesmo treinador E o mesmo item de estoque com outro despacho concorrente.
As duas coisas sao travadas na mesma transacao, em ordem deterministica — o
treinador primeiro, os itens depois, ordenados por id — antes de qualquer
validacao de dominio rodar. `calcular_despacho` so enxerga um instantaneo que
ja esta sob lock, entao a resposta dele e a resposta que vale.

**A previa e o despacho chamam a mesma funcao do dominio.** Os dois montam o
mesmo `grafo`, o mesmo `destino` e a mesma `carga`, e diferem so em travar (ou
nao) e em gravar (ou nao) no final — exatamente o padrao que
`trainers_service.definir_time`/`prever_time` ja estabeleceu na Fase 4.
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.erros import (
    ConflitoDeExpedicao,
    ExpedicaoNaoEstaEmCurso,
    LocalNaoEncontrado,
    RecursoNaoEncontrado,
)
from app.game import balance, expedition
from app.game import trainers as trainers_dominio
from app.game.expedition import ItemNaCarga, LocalDaExpedicao, TreinadorParaExpedicao
from app.game.mapa import (
    DestinoForaDeAlcance,
    GrafoDeLocais,
    LocalDesconhecido,
    LocalNoGrafo,
    montar_grafo,
)
from app.game.power import PokemonNoTime
from app.game.stats import StatsBase
from app.game.trainers import StatusTreinador
from app.models import Expedicao, Local, PokemonInstancia, Treinador
from app.repositories import expedicoes as expedicoes_repo
from app.repositories import itens as itens_repo
from app.repositories import mapa as mapa_repo
from app.repositories import treinadores as treinadores_repo
from app.schemas.expedicoes import (
    ExpedicaoLer,
    ItemDaCargaEntrada,
    ItemDaCargaLer,
    ListaExpedicoes,
    PreviaDespachoLer,
)

# --- Traducao ORM -> dominio (fronteira do Artigo I) ------------------------


def _grafo_de_locais(locais: Sequence[Local]) -> GrafoDeLocais:
    """Traduz os `Local` do ORM para o grafo que `game.mapa` entende.

    Mesma funcao de `mapa_service._montar_grafo`; duplicada aqui porque
    importar um helper privado de outro `services/` acopla os dois modulos a
    um detalhe de implementacao que nenhum dos dois promete manter.
    """
    return montar_grafo(
        LocalNoGrafo(
            id=local.id,
            custo_travessia_minutos=local.custo_travessia_minutos,
            encontros_base=local.encontros_base,
            vizinhos=tuple(local.vizinhos),
        )
        for local in locais
    )


def _local_da_expedicao(local: Local) -> LocalDaExpedicao:
    return LocalDaExpedicao(
        id=local.id,
        nivel_selvagem_min=local.nivel_selvagem_min,
        nivel_selvagem_max=local.nivel_selvagem_max,
        nivel_dificuldade=local.nivel_dificuldade,
    )


def _pokemon_no_time(pokemon: PokemonInstancia) -> PokemonNoTime:
    """`pokemon` precisa chegar com `especie` ja carregada (sem lazy load)."""
    especie = pokemon.especie
    base = StatsBase(
        hp=especie.hp_base,
        ataque=especie.ataque_base,
        defesa=especie.defesa_base,
        ataque_especial=especie.ataque_especial_base,
        defesa_especial=especie.defesa_especial_base,
        velocidade=especie.velocidade_base,
    )
    return PokemonNoTime.a_partir_dos_stats(base, pokemon.nivel, pokemon.hp_atual_pct)


def _treinador_para_expedicao(treinador: Treinador) -> TreinadorParaExpedicao:
    return TreinadorParaExpedicao(
        id=treinador.id, nivel=treinador.nivel, status=trainers_dominio.status_de(treinador.status)
    )


def _carga_para_expedicao(
    carga_pedida: Sequence[ItemDaCargaEntrada],
    *,
    quantidades_em_estoque: dict[str, int],
    efeitos_duracao: dict[str, float],
) -> tuple[ItemNaCarga, ...]:
    return tuple(
        ItemNaCarga(
            item_id=item.item_id,
            quantidade=item.quantidade,
            quantidade_em_estoque=quantidades_em_estoque.get(item.item_id, 0),
            efeito_duracao=efeitos_duracao.get(item.item_id, 0.0),
        )
        for item in carga_pedida
    )


def _destino_valido(
    sessao: Session, local_id: str
) -> tuple[GrafoDeLocais, dict[str, Local], LocalDaExpedicao]:
    """O grafo, o acervo de locais e o destino traduzido, ou 404 (criterio 13)."""
    locais = mapa_repo.listar_locais(sessao)
    locais_por_id = {local.id: local for local in locais}
    grafo = _grafo_de_locais(locais)
    try:
        grafo.local(local_id)
    except LocalDesconhecido as erro:
        raise LocalNaoEncontrado(erro) from erro
    return grafo, locais_por_id, _local_da_expedicao(locais_por_id[local_id])


def _itens_desconhecidos(
    sessao: Session, carga_pedida: Sequence[ItemDaCargaEntrada]
) -> tuple[tuple[str, ...], dict]:
    """Os ids pedidos e o catalogo correspondente, ou 404 se algum nao existe.

    O catalogo de itens e seed (Artigo V): um `item_id` que nao existe nele
    nao e carga recusavel pelo dominio, e um pedido que se refere a algo que
    nunca existiu — o mesmo tratamento de qualquer recurso ausente.
    """
    item_ids = tuple(sorted({item.item_id for item in carga_pedida}))
    catalogo = itens_repo.buscar_itens_referencia(sessao, item_ids)
    desconhecido = next((item_id for item_id in item_ids if item_id not in catalogo), None)
    if desconhecido is not None:
        raise RecursoNaoEncontrado()
    return item_ids, catalogo


# --- Leitura (criterios 9 a 11 e 13) -----------------------------------------


def _montar_expedicao_ler(expedicao: Expedicao, agora: datetime) -> ExpedicaoLer:
    """A unica funcao que traduz uma `Expedicao` para a ficha que a API devolve.

    `estado_observado` e `segundos_restantes` vem de `game.expedition`, a
    unica fonte dessas duas respostas (plan.md): dois lugares derivando por
    conta propria discordariam bem no instante em que o professor esta
    olhando.
    """
    estado = expedition.estado_observado(expedicao.status, expedicao.eta, agora)
    # Em estado terminal o `eta` deixou de significar alguma coisa: uma
    # expedicao abortada respondia com o prazo de uma viagem que nao vai mais
    # acontecer. Nulo diz "nao se aplica"; zero diria "acabou agora".
    restante = None if estado.terminal else expedition.tempo_restante(expedicao.eta, agora)
    return ExpedicaoLer(
        id=expedicao.id,
        treinador_id=expedicao.treinador_id,
        treinador_nome=expedicao.treinador.nome,
        local_destino_id=expedicao.local_destino_id,
        local_destino_nome=expedicao.local_destino.nome,
        local_origem_id=expedicao.local_origem_id,
        local_origem_nome=expedicao.local_origem.nome,
        status=expedicao.status,
        estado_observado=estado.value,
        seed=expedicao.seed,
        started_at=expedicao.started_at,
        eta=expedicao.eta,
        resolvida_em=expedicao.resolvida_em,
        duracao_minutos=expedicao.duracao_minutos,
        dificuldade_calculada=expedicao.dificuldade_calculada,
        poder_time_calculado=expedicao.poder_time_calculado,
        segundos_restantes=restante,
        carga=[
            ItemDaCargaLer(
                item_id=item.item_id,
                nome=item.item.nome,
                quantidade_levada=item.quantidade_levada,
                quantidade_consumida=item.quantidade_consumida,
            )
            for item in expedicao.itens
        ],
    )


def listar(sessao: Session, laboratorio_id: uuid.UUID, status: str | None) -> ListaExpedicoes:
    """Ativas e historico, com o `estado_observado` de cada uma calculado agora.

    O filtro compara contra o estado OBSERVADO, nao contra a coluna gravada:
    e assim que uma expedicao `EM_CURSO` cujo `eta` ja passou sai da lista de
    "em curso" e entra na de "aguardando relatorio" sem que nenhuma escrita
    tenha acontecido no banco.

    Aceita VARIOS estados justamente por isso. O painel de ativas quer ver
    "em curso OU aguardando relatorio", e pedindo so `EM_CURSO` a expedicao
    sumia da tela no instante em que terminava — o momento em que o professor
    mais quer olhar para ela.
    """
    agora = datetime.now(UTC)
    expedicoes = expedicoes_repo.listar(sessao, laboratorio_id)
    linhas = [_montar_expedicao_ler(expedicao, agora) for expedicao in expedicoes]
    if status:
        procurados = set(status)
        linhas = [linha for linha in linhas if linha.estado_observado in procurados]
    return ListaExpedicoes(items=linhas, total=len(linhas))


def obter(sessao: Session, laboratorio_id: uuid.UUID, expedicao_id: uuid.UUID) -> ExpedicaoLer:
    expedicao = expedicoes_repo.buscar_detalhe(sessao, laboratorio_id, expedicao_id)
    if expedicao is None:
        raise RecursoNaoEncontrado()
    return _montar_expedicao_ler(expedicao, datetime.now(UTC))


# --- Despacho (criterios 1 a 8 e 14) -----------------------------------------


def despachar(
    sessao: Session,
    laboratorio_id: uuid.UUID,
    treinador_id: uuid.UUID,
    local_id: str,
    carga_pedida: Sequence[ItemDaCargaEntrada],
) -> ExpedicaoLer:
    """Despacha sob lock duplo (Artigo VII, plan.md secao 5): treinador e estoque.

    A ordem importa. Primeiro o que nao precisa de lock nenhum — existencia do
    local e do catalogo de itens, leitura pura de referencia — porque recusar
    cedo nao trava linha nenhuma a toa. So depois vem o lock do treinador e,
    por ultimo, o lock das linhas de estoque, sempre ordenadas por `item_id`:
    e essa ordem fixa, igual nos dois lados de uma corrida, que impede
    deadlock entre dois despachos concorrentes disputando os mesmos itens.
    """
    agora = datetime.now(UTC)
    escala = get_settings().expedition_time_scale

    grafo, _locais_por_id, destino = _destino_valido(sessao, local_id)
    visitados = mapa_repo.listar_visitados(sessao, laboratorio_id)
    item_ids, catalogo = _itens_desconhecidos(sessao, carga_pedida)

    treinador = treinadores_repo.travar_treinador_com_time(sessao, laboratorio_id, treinador_id)
    if treinador is None:
        raise RecursoNaoEncontrado()

    quantidades = itens_repo.travar_quantidades(sessao, laboratorio_id, item_ids)
    carga = _carga_para_expedicao(
        carga_pedida,
        quantidades_em_estoque=quantidades,
        efeitos_duracao={item_id: item.efeito_duracao for item_id, item in catalogo.items()},
    )

    seed = random.randrange(balance.SEED_MAXIMO)

    try:
        despacho = expedition.calcular_despacho(
            treinador=_treinador_para_expedicao(treinador),
            time=[_pokemon_no_time(pokemon) for pokemon in treinador.time],
            grafo=grafo,
            visitados=visitados,
            destino=destino,
            seed=seed,
            agora=agora,
            carga=carga,
            escala=escala,
        )
    except LocalDesconhecido as erro:  # pragma: no cover - ja validado em _destino_valido
        sessao.rollback()
        raise LocalNaoEncontrado(erro) from erro
    except (expedition.ErroDeExpedicao, DestinoForaDeAlcance) as erro:
        sessao.rollback()
        raise ConflitoDeExpedicao(erro) from erro

    for item_id, quantidade in despacho.debitos:
        debitado = itens_repo.debitar_condicional(sessao, laboratorio_id, item_id, quantidade)
        if not debitado:
            # So acontece se o instantaneo travado e a validacao de dominio
            # discordarem por um bug anterior: a leitura sob lock ja garantiu
            # estoque suficiente. Recusar aqui em vez de prosseguir e a
            # segunda linha de defesa do invariante 9.
            sessao.rollback()
            raise ConflitoDeExpedicao(
                expedition.EstoqueInsuficiente(
                    f"Nao ha mais {quantidade} de {item_id!r} disponivel no estoque.",
                    detalhes={"item_id": item_id, "quantidade": quantidade},
                )
            )

    treinadores_repo.atualizar_status(treinador, StatusTreinador.EM_EXPEDICAO)
    expedicao = expedicoes_repo.criar(sessao, laboratorio_id=laboratorio_id, despacho=despacho)
    sessao.commit()

    atualizada = expedicoes_repo.buscar_detalhe(sessao, laboratorio_id, expedicao.id)
    if atualizada is None:  # pragma: no cover - impossivel, acabamos de gravar
        raise RecursoNaoEncontrado()
    return _montar_expedicao_ler(atualizada, datetime.now(UTC))


def prever(
    sessao: Session,
    laboratorio_id: uuid.UUID,
    treinador_id: uuid.UUID,
    local_id: str,
    carga_pedida: Sequence[ItemDaCargaEntrada],
) -> PreviaDespachoLer:
    """A mesma validacao do despacho, sem lock e sem gravar (plan.md secao 8).

    Sem lock de proposito: a previa nao escreve nada, entao nao ha o que
    proteger de concorrencia aqui. O `POST /expeditions` revalida tudo sob
    lock antes de gravar, e e essa segunda validacao que vale — a previa so
    existe para o professor nao levar um erro no botao de despachar.
    """
    agora = datetime.now(UTC)
    escala = get_settings().expedition_time_scale

    grafo, _locais_por_id, destino = _destino_valido(sessao, local_id)
    visitados = mapa_repo.listar_visitados(sessao, laboratorio_id)
    item_ids, catalogo = _itens_desconhecidos(sessao, carga_pedida)

    treinador = treinadores_repo.buscar_detalhe(sessao, laboratorio_id, treinador_id)
    if treinador is None:
        raise RecursoNaoEncontrado()

    quantidades = itens_repo.buscar_quantidades(sessao, laboratorio_id, item_ids)
    carga = _carga_para_expedicao(
        carga_pedida,
        quantidades_em_estoque=quantidades,
        efeitos_duracao={item_id: item.efeito_duracao for item_id, item in catalogo.items()},
    )

    # A semente da previa nunca e gravada e nunca decide nada que o professor
    # veja: zero e um valor valido qualquer, escolhido no lugar de sortear
    # aleatoriedade que ninguem vai usar.
    previa = expedition.prever_despacho(
        treinador=_treinador_para_expedicao(treinador),
        time=[_pokemon_no_time(pokemon) for pokemon in treinador.time],
        grafo=grafo,
        visitados=visitados,
        destino=destino,
        seed=0,
        agora=agora,
        carga=carga,
        escala=escala,
    )

    if not previa.valido or previa.despacho is None:
        return PreviaDespachoLer(valido=False, codigo=previa.codigo, motivo=previa.motivo)

    despacho = previa.despacho
    return PreviaDespachoLer(
        valido=True,
        duracao_minutos=despacho.duracao_minutos,
        eta_estimado=despacho.eta,
        dificuldade=despacho.dificuldade,
        chance_estimada=despacho.chance_estimada,
        capacidade_bagagem=despacho.capacidade_bagagem,
    )


# --- Aborto (criterio 12) ----------------------------------------------------


def abortar(sessao: Session, laboratorio_id: uuid.UUID, expedicao_id: uuid.UUID) -> ExpedicaoLer:
    """Aborta sob lock (Artigo VII): o treinador volta na hora, os itens nao.

    So aborta quem esta de fato `EM_CURSO` agora — nao so na coluna, no estado
    OBSERVADO. Uma expedicao cujo `eta` ja passou esta `AGUARDANDO_RELATORIO`:
    a missao ja acabou na pratica, e abortar neste ponto so apagaria a chance
    de a Fase 7 gerar relatorio e recompensa dela. A spec fala em abortar uma
    expedicao "em andamento", e isto deixou de ser andamento (decisao
    registrada em `ExpedicaoNaoEstaEmCurso`).
    """
    agora = datetime.now(UTC)
    expedicao = expedicoes_repo.travar_para_abortar(sessao, laboratorio_id, expedicao_id)
    if expedicao is None:
        raise RecursoNaoEncontrado()

    estado = expedition.estado_observado(expedicao.status, expedicao.eta, agora)
    if estado is not expedition.EstadoObservado.EM_CURSO:
        sessao.rollback()
        raise ExpedicaoNaoEstaEmCurso()

    expedicao.status = expedition.StatusExpedicao.ABORTADA.value

    treinador = treinadores_repo.travar_treinador(sessao, laboratorio_id, expedicao.treinador_id)
    if treinador is not None:
        treinadores_repo.atualizar_status(treinador, StatusTreinador.DISPONIVEL)

    sessao.commit()

    atualizada = expedicoes_repo.buscar_detalhe(sessao, laboratorio_id, expedicao_id)
    if atualizada is None:  # pragma: no cover - impossivel, acabamos de gravar
        raise RecursoNaoEncontrado()
    return _montar_expedicao_ler(atualizada, datetime.now(UTC))
