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
    ConflitoDeViveiro,
    ExpedicaoAbortada,
    ExpedicaoEmCurso,
    ExpedicaoNaoEstaEmCurso,
    LocalNaoEncontrado,
    RecursoNaoEncontrado,
)
from app.game import balance, expedition
from app.game import encounter as encounter_dominio
from app.game import laboratorio as laboratorio_dominio
from app.game import trainers as trainers_dominio
from app.game import viveiro as viveiro_dominio
from app.game.expedition import (
    CatalogoEmCampo,
    ContextoDeResolucao,
    DestinoEmCampo,
    EspecieEmCampo,
    ItemNaCarga,
    LocalDaExpedicao,
    PokemonDaExpedicao,
    RelatorioDeCampo,
    TreinadorEmCampo,
    TreinadorParaExpedicao,
)
from app.game.itens import ItemDaMochila, categoria_de
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
from app.repositories import especies as especies_repo
from app.repositories import expedicoes as expedicoes_repo
from app.repositories import itens as itens_repo
from app.repositories import laboratorios as laboratorios_repo
from app.repositories import mapa as mapa_repo
from app.repositories import pokedex as pokedex_repo
from app.repositories import pokemon as pokemon_repo
from app.repositories import treinadores as treinadores_repo
from app.schemas.expedicoes import (
    CapturaDoRelatorioLer,
    EspecieVistaLer,
    EventoDeExpedicaoLer,
    ExpedicaoClaimLer,
    ExpedicaoLer,
    ExpedicaoResumoLer,
    GanhoDeExperienciaLer,
    ItemDaCargaEntrada,
    ItemDaCargaLer,
    ItemDoRelatorioLer,
    ListaExpedicoes,
    PokemonDoRelatorioLer,
    PreviaDespachoLer,
    RelatorioDeCampoLer,
)
from app.schemas.pokemon import PokemonResumo
from app.services import relogio
from app.services.trainers import avatar_para_ler

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


def _stats_base_da_especie(pokemon: PokemonInstancia) -> StatsBase:
    especie = pokemon.especie
    return StatsBase(
        hp=especie.hp_base,
        ataque=especie.ataque_base,
        defesa=especie.defesa_base,
        ataque_especial=especie.ataque_especial_base,
        defesa_especial=especie.defesa_especial_base,
        velocidade=especie.velocidade_base,
    )


def _pokemon_no_time(pokemon: PokemonInstancia) -> PokemonNoTime:
    """`pokemon` precisa chegar com `especie` ja carregada (sem lazy load).

    Le `hp_atual_pct` CRU: so e correto chamar isto depois que o HP ja foi
    materializado (despacho) ou quando o Pokemon esta em campo, onde o
    invariante 18 ja garante que o valor gravado e o observado (a enfermaria
    nao anda durante a expedicao).
    """
    return PokemonNoTime.a_partir_dos_stats(
        _stats_base_da_especie(pokemon), pokemon.nivel, pokemon.hp_atual_pct
    )


def _pokemon_no_time_observado(
    pokemon: PokemonInstancia, *, agora: datetime, escala: float
) -> PokemonNoTime:
    """Como `_pokemon_no_time`, mas com o HP OBSERVADO agora, sem gravar nada.

    Usada pela previa (`prever`), que nunca escreve: mostrar o poder com o HP
    cru subestimaria um time que ja recuperou boa parte do dano no
    laboratorio.
    """
    pct = relogio.hp_observado(
        pokemon.hp_atual_pct, pokemon.hp_atualizado_em, agora=agora, escala=escala
    )
    return PokemonNoTime.a_partir_dos_stats(_stats_base_da_especie(pokemon), pokemon.nivel, pct)


def _materializar_hp(pokemon: PokemonInstancia, *, agora: datetime, escala: float) -> None:
    """Grava o HP ja recuperado e carimba `agora` (tarefa 12, SDD 4.8).

    Chamada no despacho, antes de montar o time para `calcular_despacho`: a
    partir daqui a enfermaria para (invariante 18), e o desgaste da expedicao
    incide sobre este valor, nao sobre o que o banco teria em outro instante —
    e isso que mantem a resolucao futura funcao so da semente e do envio.
    """
    pokemon.hp_atual_pct = relogio.hp_observado(
        pokemon.hp_atual_pct, pokemon.hp_atualizado_em, agora=agora, escala=escala
    )
    pokemon.hp_atualizado_em = agora


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


def _campos_comuns_ler(expedicao: Expedicao, agora: datetime, escala: float) -> dict:
    """Os campos que `ExpedicaoResumoLer` e `ExpedicaoLer` compartilham.

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
    return {
        "id": expedicao.id,
        "treinador_id": expedicao.treinador_id,
        "treinador_nome": expedicao.treinador.nome,
        "treinador_avatar": avatar_para_ler(expedicao.treinador.avatar),
        # O HP vem DERIVADO, pela mesma funcao que a ficha do treinador usa, e
        # nao do valor cru: dois lugares mostrando HP diferente para o mesmo
        # Pokemon foi defeito na Fase 7. Em expedicao a recuperacao nao corre
        # (invariante 18), e e a propria funcao que sabe disso.
        "treinador_time": [
            PokemonResumo.de_modelo(
                pokemon,
                hp_atual_pct=relogio.hp_observado(
                    pokemon.hp_atual_pct,
                    pokemon.hp_atualizado_em,
                    agora=agora,
                    escala=escala,
                ),
            )
            for pokemon in expedicao.treinador.time
        ],
        "local_destino_id": expedicao.local_destino_id,
        "local_destino_nome": expedicao.local_destino.nome,
        "local_origem_id": expedicao.local_origem_id,
        "local_origem_nome": expedicao.local_origem.nome,
        "status": expedicao.status,
        "estado_observado": estado.value,
        "seed": expedicao.seed,
        "started_at": expedicao.started_at,
        "eta": expedicao.eta,
        "resolvida_em": expedicao.resolvida_em,
        "duracao_minutos": expedicao.duracao_minutos,
        "dificuldade_calculada": expedicao.dificuldade_calculada,
        "poder_time_calculado": expedicao.poder_time_calculado,
        "segundos_restantes": restante,
        "carga": [
            ItemDaCargaLer(
                item_id=item.item_id,
                nome=item.item.nome,
                quantidade_levada=item.quantidade_levada,
                quantidade_consumida=item.quantidade_consumida,
            )
            for item in expedicao.itens
        ],
    }


def _montar_expedicao_resumo(
    expedicao: Expedicao, agora: datetime, escala: float
) -> ExpedicaoResumoLer:
    """A linha de `GET /expeditions` (revisao da Fase 7, achado 1): sem relatorio.

    Usada so pela listagem. Nunca chama `_montar_relatorio_ler`: o ponto desta
    funcao e justamente nao pagar o custo de montar a linha do tempo inteira
    de cada expedicao so para o painel mostrar um cartao.
    """
    return ExpedicaoResumoLer(**_campos_comuns_ler(expedicao, agora, escala))


def _montar_expedicao_ler(
    expedicao: Expedicao, agora: datetime, escala: float
) -> ExpedicaoLer:
    """A ficha completa que `GET /expeditions/{id}` e o `claim` devolvem.

    A unica diferenca para `_montar_expedicao_resumo` e o relatorio: aqui,
    sim, vale a pena montar a linha do tempo inteira, porque e exatamente o
    que o professor pediu ao abrir esta expedicao especifica.
    """
    return ExpedicaoLer(
        **_campos_comuns_ler(expedicao, agora, escala),
        relatorio=_montar_relatorio_ler(expedicao),
    )


def listar(
    sessao: Session,
    laboratorio_id: uuid.UUID,
    status: str | None,
    limite: int = expedicoes_repo.LIMITE_PADRAO,
) -> ListaExpedicoes:
    """As `limite` expedicoes mais recentes do laboratorio, sem relatorio.

    O filtro de `status` compara contra o estado OBSERVADO, nao contra a
    coluna gravada: e assim que uma expedicao `EM_CURSO` cujo `eta` ja passou
    sai da lista de "em curso" e entra na de "aguardando relatorio" sem que
    nenhuma escrita tenha acontecido no banco.

    Aceita VARIOS estados justamente por isso. O painel de ativas quer ver
    "em curso OU aguardando relatorio", e pedindo so `EM_CURSO` a expedicao
    sumia da tela no instante em que terminava — o momento em que o professor
    mais quer olhar para ela.

    `limite` corta a consulta no banco (revisao da Fase 7, achado 1), nao a
    lista depois de filtrar: o filtro de `status` incide sobre as `limite`
    mais recentes, nao sobre o historico inteiro do laboratorio. Isso casa com
    o uso real — o painel de ativas tem poucas linhas (nunca mais que o
    tamanho do corpo de treinadores) e sempre cabe dentro do teto padrao; o
    historico aceita um `limite` maior quando o professor pedir.
    """
    agora = datetime.now(UTC)
    escala = get_settings().expedition_time_scale
    expedicoes = expedicoes_repo.listar(sessao, laboratorio_id, limite)
    linhas = [_montar_expedicao_resumo(expedicao, agora, escala) for expedicao in expedicoes]
    if status:
        procurados = set(status)
        linhas = [linha for linha in linhas if linha.estado_observado in procurados]
    return ListaExpedicoes(items=linhas, total=len(linhas))


def obter(sessao: Session, laboratorio_id: uuid.UUID, expedicao_id: uuid.UUID) -> ExpedicaoLer:
    expedicao = expedicoes_repo.buscar_detalhe(sessao, laboratorio_id, expedicao_id)
    if expedicao is None:
        raise RecursoNaoEncontrado()
    return _montar_expedicao_ler(
        expedicao, datetime.now(UTC), get_settings().expedition_time_scale
    )


# --- Despacho (criterios 1 a 8 e 14) -----------------------------------------


def _exigir_espaco_no_viveiro(sessao: Session, laboratorio_id: uuid.UUID) -> None:
    """A GUARDA do viveiro transbordado (tarefa 15 da spec 008, regra 4).

    Chamada de DOIS lugares so, `despachar` e `prever` — nunca em reclamar
    relatorio, aceitar entrega, concluir entrega ou soltar, que sao as
    saidas do transbordo — e as DUAS chamadas passam por esta MESMA funcao,
    nao por duas copias da mesma conta. A previa divergindo do despacho ja
    foi defeito nas Fases 4 e 6 (time e expedicao validando por caminhos
    diferentes); a cura aqui nao e "lembrar de testar os dois toda vez", e
    sim deixar fisicamente impossivel ter dois lugares que decidem a mesma
    pergunta de jeitos diferentes.

    Leitura sem lock: nem o despacho nem a previa mudam a ocupacao do
    viveiro, entao nao ha nada aqui para proteger de concorrencia alem do
    que o lock do treinador, no despacho, ja cobre.
    """
    ocupacao_do_viveiro = pokemon_repo.contar_viveiro(sessao, laboratorio_id)
    viveiro_dominio.exigir_espaco_para_despachar(ocupacao_do_viveiro)


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

    try:
        _exigir_espaco_no_viveiro(sessao, laboratorio_id)
    except viveiro_dominio.ViveiroTransbordado as erro:
        raise ConflitoDeViveiro(erro) from erro

    grafo, _locais_por_id, destino = _destino_valido(sessao, local_id)
    visitados = mapa_repo.listar_visitados(sessao, laboratorio_id)
    item_ids, catalogo = _itens_desconhecidos(sessao, carga_pedida)
    # Retrato da Pokedex NO ENVIO (achado 3 da revisao da Fase 7): gravado na
    # expedicao abaixo, para que a resolucao nunca precise ler a Pokedex ao
    # vivo no `claim` (invariante 19, SDD 3.3).
    especies_vistas_no_envio = pokedex_repo.buscar_vistas(sessao, laboratorio_id)

    treinador = treinadores_repo.travar_treinador_com_time(sessao, laboratorio_id, treinador_id)
    if treinador is None:
        raise RecursoNaoEncontrado()

    # Tarefa 12 (spec 007): materializa o HP ja recuperado e para o relogio
    # da enfermaria para este time, ANTES de calcular o poder — o desgaste da
    # resolucao futura vai incidir sobre este valor, nunca sobre o que o
    # banco teria num instante diferente (invariante 18, Artigo III).
    for pokemon in treinador.time:
        _materializar_hp(pokemon, agora=agora, escala=escala)

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
    expedicao = expedicoes_repo.criar(
        sessao,
        laboratorio_id=laboratorio_id,
        despacho=despacho,
        especies_vistas_no_envio=especies_vistas_no_envio,
    )
    sessao.commit()

    atualizada = expedicoes_repo.buscar_detalhe(sessao, laboratorio_id, expedicao.id)
    if atualizada is None:  # pragma: no cover - impossivel, acabamos de gravar
        raise RecursoNaoEncontrado()
    return _montar_expedicao_ler(
        atualizada, datetime.now(UTC), get_settings().expedition_time_scale
    )


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

    A guarda do viveiro transbordado (regra 4) e a MESMA chamada de
    `despachar`, via `_exigir_espaco_no_viveiro` — nao uma copia dela. Sem
    isso, esta previa diria "pode despachar" com o viveiro transbordado, e o
    `POST /expeditions` recusaria logo em seguida: exatamente o erro no botao
    que esta funcao existe para evitar (achado da revisao da Fase 8).
    """
    agora = datetime.now(UTC)
    escala = get_settings().expedition_time_scale

    try:
        _exigir_espaco_no_viveiro(sessao, laboratorio_id)
    except viveiro_dominio.ViveiroTransbordado as erro:
        return PreviaDespachoLer(valido=False, codigo=erro.codigo, motivo=str(erro))

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
        time=[
            _pokemon_no_time_observado(pokemon, agora=agora, escala=escala)
            for pokemon in treinador.time
        ],
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

    Carimba `hp_atualizado_em = agora` em cada Pokemon do time que volta
    (achado 2 da revisao da Fase 7): sem isso, o carimbo continuava sendo o
    instante da PARTIDA, gravado por `_materializar_hp` no despacho. Como a
    recuperacao passiva fica suspensa so enquanto o treinador esta
    `EM_EXPEDICAO` (invariante 18), o instante em que ele volta a
    `DISPONIVEL` e o instante em que o relogio da enfermaria passa a contar —
    e se o marco continuasse no passado, a primeira leitura seguinte creditaria
    de uma vez todo o tempo que o time passou em campo, como se tivesse
    passado parado no laboratorio o tempo todo. O HP gravado (`hp_atual_pct`)
    nao muda aqui, so o marco — exatamente o papel que `_gravar_resultado` da
    a `resolvida_em` do lado do sucesso.
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
        # Trava os Pokemon do time (pedido vazio: `travar_pokemon_envolvidos`
        # ja inclui quem esta com `treinador_id == treinador.id`) para
        # recarimbar o marco da enfermaria sob a mesma transacao que libera o
        # treinador.
        time = treinadores_repo.travar_pokemon_envolvidos(sessao, laboratorio_id, treinador.id, ())
        for pokemon in time:
            pokemon.hp_atualizado_em = agora

    sessao.commit()

    atualizada = expedicoes_repo.buscar_detalhe(sessao, laboratorio_id, expedicao_id)
    if atualizada is None:  # pragma: no cover - impossivel, acabamos de gravar
        raise RecursoNaoEncontrado()
    return _montar_expedicao_ler(
        atualizada, datetime.now(UTC), get_settings().expedition_time_scale
    )


# --- Relatorio de campo (spec 007, ADR-006) ----------------------------------
#
# `claim` e o coracao da fase: ele abre a UNICA transacao em que a expedicao
# e resolvida, trava a linha, monta o `ContextoDeResolucao`, chama
# `expedition.resolver` e grava tudo que voltou. O servico nao decide NADA de
# jogo aqui — todo `if` sobre regra pertence a `game/`, e o que resta e
# buscar estado, montar o retrato imutavel que o dominio pede, e persistir o
# resultado exatamente como ele saiu.


def _especie_em_campo(especie) -> EspecieEmCampo:
    return EspecieEmCampo.a_partir_dos_stats(
        id=especie.id,
        nome=especie.nome,
        experiencia_base=especie.experiencia_base,
        taxa_captura=especie.taxa_captura,
        curva_crescimento=especie.curva_crescimento,
        stats_base=StatsBase(
            hp=especie.hp_base,
            ataque=especie.ataque_base,
            defesa=especie.defesa_base,
            ataque_especial=especie.ataque_especial_base,
            defesa_especial=especie.defesa_especial_base,
            velocidade=especie.velocidade_base,
        ),
        evolui_para_id=especie.evolui_para_id,
        evolui_em_nivel=especie.evolui_em_nivel,
    )


def _montar_catalogo(
    sessao: Session, time: Sequence[PokemonInstancia], linhas_raw: Sequence
) -> CatalogoEmCampo:
    """O catalogo COMPLETO que `ContextoDeResolucao` exige: toda especie do
    time, toda especie da tabela de encontros e toda a cadeia de evolucao
    delas (nao-negociavel: um catalogo parcial e recusado na construcao)."""
    ids = {pokemon.especie_id for pokemon in time} | {linha.especie_id for linha in linhas_raw}
    especies = especies_repo.buscar_catalogo(sessao, ids)
    return {especie_id: _especie_em_campo(especie) for especie_id, especie in especies.items()}


def _montar_contexto(
    sessao: Session, expedicao: Expedicao, treinador: Treinador
) -> ContextoDeResolucao:
    linhas_raw = mapa_repo.buscar_linhas_de_encontro(sessao, expedicao.local_destino_id)
    catalogo = _montar_catalogo(sessao, treinador.time, linhas_raw)

    time = tuple(
        PokemonDaExpedicao(
            id=pokemon.id,
            especie_id=pokemon.especie_id,
            nivel=pokemon.nivel,
            experiencia=pokemon.experiencia,
            hp_atual_pct=pokemon.hp_atual_pct,
        )
        for pokemon in treinador.time
    )
    # `buscar_linhas_de_encontro` ja devolve em ordem canonica (especie_id
    # crescente); `ordenar_linhas` so entraria em cena para uma fonte sem
    # essa garantia, que nao e o caso de uma consulta com `ORDER BY`.
    linhas = tuple(
        encounter_dominio.LinhaDeEncontro(
            especie_id=linha.especie_id,
            peso=linha.peso,
            nivel_min=linha.nivel_min,
            nivel_max=linha.nivel_max,
        )
        for linha in linhas_raw
    )
    destino = DestinoEmCampo(
        local=_local_da_expedicao(expedicao.local_destino),
        nome=expedicao.local_destino.nome,
        encontros_base=expedicao.local_destino.encontros_base,
        linhas_de_encontro=linhas,
    )
    # Primeira resolucao desta expedicao (o estado so chega aqui vindo de
    # AGUARDANDO_RELATORIO): `quantidade_consumida` ainda e zero, entao o que
    # resta na carga e exatamente o que foi levado.
    carga = tuple(
        ItemDaMochila(
            item_id=item.item_id,
            nome=item.item.nome,
            categoria=categoria_de(item.item.categoria),
            potencia=item.item.potencia,
            quantidade=item.quantidade_levada - item.quantidade_consumida,
        )
        for item in expedicao.itens
    )
    # Retrato do ENVIO, nunca uma leitura ao vivo (achado 3 da revisao da Fase
    # 7, invariante 19): ler a Pokedex aqui, no `claim`, era o bug — fora de
    # qualquer lock, dois `claim`s concorrentes do mesmo laboratorio liam a
    # mesma Pokedex "antes de qualquer um gravar" e os dois anunciavam
    # DESCOBERTA da mesma especie. `especies_vistas_no_envio` foi gravada por
    # `despachar()` no instante do despacho e nunca muda depois.
    especies_vistas = set(expedicao.especies_vistas_no_envio)

    ids_para_nome = {item_id for item_id, _ in balance.TABELA_DE_ACHADOS} | {
        item.item_id for item in expedicao.itens
    }
    nomes_de_itens = {
        item_id: item.nome
        for item_id, item in itens_repo.buscar_itens_referencia(
            sessao, tuple(ids_para_nome)
        ).items()
    }

    return ContextoDeResolucao(
        treinador=TreinadorEmCampo(id=treinador.id, nome=treinador.nome, nivel=treinador.nivel),
        time=time,
        destino=destino,
        origem_nome=expedicao.local_origem.nome,
        catalogo=catalogo,
        carga=carga,
        especies_vistas=frozenset(especies_vistas),
        nomes_de_itens=nomes_de_itens,
        duracao_minutos=expedicao.duracao_minutos,
    )


def _item_resumo(item) -> dict:
    return {"item_id": item.item_id, "nome": item.nome, "quantidade": item.quantidade}


def _montar_resumo(
    relatorio: RelatorioDeCampo,
    *,
    capturas_pokemon_ids: Sequence[uuid.UUID],
    treinador_nivel_antes: int,
    treinador_nivel_depois: int,
    laboratorio_nivel_antes: int,
    laboratorio_nivel_depois: int,
    local_desbloqueado: bool,
) -> dict:
    """Tudo que o relatorio mostra ALEM da linha do tempo (que mora em
    `expedicao_eventos`). Gravado uma vez em `relatorio_resumo` e so lido
    depois — nunca recalculado — porque treinador e laboratorio continuam
    ganhando experiencia em expedicoes futuras, e o relatorio desta precisa
    continuar dizendo o que ELA rendeu, nao o estado atual dos dois.
    """
    return {
        "encontros": relatorio.encontros,
        "vitorias": relatorio.vitorias,
        "derrotas": relatorio.derrotas,
        "local_desbloqueado": local_desbloqueado,
        "capturas": [
            {
                "especie_id": captura.especie_id,
                "especie_nome": captura.especie_nome,
                "nivel": captura.nivel,
                "pokemon_id": str(pokemon_id),
            }
            for captura, pokemon_id in zip(relatorio.capturas, capturas_pokemon_ids, strict=True)
        ],
        "time": [
            {
                "pokemon_id": str(membro.pokemon_id),
                "especie_id": membro.especie_id,
                "especie_nome": membro.especie_nome,
                "nivel_antes": membro.nivel_antes,
                "nivel_depois": membro.nivel_depois,
                "exp_ganha": membro.experiencia_ganha,
                "hp_antes_pct": membro.hp_antes_pct,
                "hp_depois_pct": membro.hp_depois_pct,
                "evoluiu_para_id": membro.evoluiu_para_id,
                "evoluiu_para_nome": membro.evoluiu_para_nome,
            }
            for membro in relatorio.time
        ],
        "treinador": {
            "nivel_antes": treinador_nivel_antes,
            "nivel_depois": treinador_nivel_depois,
            "exp_ganha": relatorio.experiencia_treinador,
        },
        "laboratorio": {
            "nivel_antes": laboratorio_nivel_antes,
            "nivel_depois": laboratorio_nivel_depois,
            "exp_ganha": relatorio.experiencia_laboratorio,
        },
        "itens_consumidos": [_item_resumo(item) for item in relatorio.itens_consumidos],
        "itens_encontrados": [_item_resumo(item) for item in relatorio.itens_encontrados],
        "especies_vistas": [
            {"especie_id": av.especie_id, "nome": av.especie_nome, "primeira_vez": av.primeira_vez}
            for av in relatorio.avistamentos
        ],
    }


def _gravar_resultado(
    sessao: Session,
    expedicao: Expedicao,
    treinador: Treinador,
    relatorio: RelatorioDeCampo,
    *,
    agora: datetime,
) -> None:
    """Grava exatamente o que `relatorio` trouxe, tudo na transacao do `claim` (regra 14)."""
    expedicoes_repo.gravar_eventos(sessao, expedicao.id, relatorio.eventos)
    expedicoes_repo.atualizar_consumo_itens(sessao, expedicao.id, relatorio.itens_consumidos)

    for item in relatorio.itens_encontrados:
        itens_repo.creditar(sessao, expedicao.laboratorio_id, item.item_id, item.quantidade)

    pokemon_por_id = {pokemon.id: pokemon for pokemon in treinador.time}
    for membro in relatorio.time:
        pokemon_repo.atualizar_apos_expedicao(
            pokemon_por_id[membro.pokemon_id],
            nivel=membro.nivel_depois,
            experiencia=membro.experiencia_depois,
            especie_id=membro.especie_final_id,
            hp_atual_pct=membro.hp_depois_pct,
            hp_atualizado_em=agora,
        )

    capturas_pokemon_ids: list[uuid.UUID] = []
    for captura in relatorio.capturas:
        novo_id = uuid.uuid4()
        capturas_pokemon_ids.append(novo_id)
        pokemon_repo.criar_capturado(
            sessao,
            id=novo_id,
            laboratorio_id=expedicao.laboratorio_id,
            especie_id=captura.especie_id,
            nivel=captura.nivel,
            experiencia=captura.experiencia,
            hp_atual_pct=captura.hp_atual_pct,
            local_captura_id=expedicao.local_destino_id,
            capturado_em=agora,
        )

    especies_capturadas = {captura.especie_id for captura in relatorio.capturas}
    pokedex_repo.registrar_avistamentos(
        sessao,
        expedicao.laboratorio_id,
        expedicao.local_destino_id,
        relatorio.avistamentos,
        especies_capturadas,
        agora,
    )

    local_desbloqueado = False
    if relatorio.desbloqueia_destino:
        local_desbloqueado = mapa_repo.desbloquear(
            sessao, expedicao.laboratorio_id, expedicao.local_destino_id, agora
        )

    nivel_treinador_antes = treinador.nivel
    experiencia_treinador = treinador.experiencia + relatorio.experiencia_treinador
    nivel_treinador_depois = trainers_dominio.nivel_para_experiencia(experiencia_treinador)
    treinadores_repo.concluir_expedicao(
        treinador, nivel=nivel_treinador_depois, experiencia=experiencia_treinador
    )

    laboratorio = laboratorios_repo.travar(sessao, expedicao.laboratorio_id)
    if laboratorio is None:  # pragma: no cover - FK garante a existencia
        raise RecursoNaoEncontrado()
    nivel_laboratorio_antes = laboratorio.nivel
    nivel_laboratorio_depois = laboratorio.nivel
    if relatorio.sucesso and relatorio.experiencia_laboratorio:
        experiencia_laboratorio = laboratorio.experiencia + relatorio.experiencia_laboratorio
        nivel_laboratorio_depois = laboratorio_dominio.nivel_para_experiencia(
            experiencia_laboratorio
        )
        laboratorios_repo.atualizar_progressao(
            laboratorio, nivel=nivel_laboratorio_depois, experiencia=experiencia_laboratorio
        )

    resumo = _montar_resumo(
        relatorio,
        capturas_pokemon_ids=capturas_pokemon_ids,
        treinador_nivel_antes=nivel_treinador_antes,
        treinador_nivel_depois=nivel_treinador_depois,
        laboratorio_nivel_antes=nivel_laboratorio_antes,
        laboratorio_nivel_depois=nivel_laboratorio_depois,
        local_desbloqueado=local_desbloqueado,
    )
    expedicoes_repo.marcar_resolvida(
        expedicao, status=relatorio.status.value, resolvida_em=agora, resumo=resumo
    )


def _montar_relatorio_ler(expedicao: Expedicao) -> RelatorioDeCampoLer | None:
    """Reconstroi o relatorio do que ja esta GRAVADO — nunca reexecuta `resolver`.

    Reexecutar daria o mesmo resultado hoje e um resultado diferente no dia em
    que uma constante de `balance.py` mudar (ADR-006): o relatorio gravado e a
    verdade, e e por isso que ele le `relatorio_resumo` e os eventos, nunca o
    estado atual de treinador, laboratorio ou pokemon_instancias.
    """
    if expedicao.resolvida_em is None or expedicao.relatorio_resumo is None:
        return None
    resumo = expedicao.relatorio_resumo
    eventos = sorted(expedicao.eventos, key=lambda evento: evento.ordem)
    return RelatorioDeCampoLer(
        status=expedicao.status,
        resolvida_em=expedicao.resolvida_em,
        encontros=resumo["encontros"],
        vitorias=resumo["vitorias"],
        derrotas=resumo["derrotas"],
        local_desbloqueado=resumo["local_desbloqueado"],
        eventos=[
            EventoDeExpedicaoLer(
                ordem=evento.ordem,
                tipo=evento.tipo,
                texto=evento.texto,
                ocorrido_em_minuto=evento.ocorrido_em_minuto,
                payload=evento.payload,
            )
            for evento in eventos
        ],
        capturas=[CapturaDoRelatorioLer(**item) for item in resumo["capturas"]],
        time=[PokemonDoRelatorioLer(**item) for item in resumo["time"]],
        treinador=GanhoDeExperienciaLer(**resumo["treinador"]),
        laboratorio=GanhoDeExperienciaLer(**resumo["laboratorio"]),
        itens_consumidos=[ItemDoRelatorioLer(**item) for item in resumo["itens_consumidos"]],
        itens_encontrados=[ItemDoRelatorioLer(**item) for item in resumo["itens_encontrados"]],
        especies_vistas=[EspecieVistaLer(**item) for item in resumo["especies_vistas"]],
    )


def _resposta_do_claim(
    sessao: Session, laboratorio_id: uuid.UUID, expedicao_id: uuid.UUID, agora: datetime
) -> ExpedicaoClaimLer:
    atualizada = expedicoes_repo.buscar_detalhe(sessao, laboratorio_id, expedicao_id)
    if atualizada is None:  # pragma: no cover - impossivel, acabamos de gravar ou de ler
        raise RecursoNaoEncontrado()
    relatorio_ler = _montar_relatorio_ler(atualizada)
    if relatorio_ler is None:  # pragma: no cover - so chega aqui ja resolvida
        raise RecursoNaoEncontrado()
    return ExpedicaoClaimLer(
        expedicao=_montar_expedicao_ler(
            atualizada, agora, get_settings().expedition_time_scale
        ),
        relatorio=relatorio_ler,
    )


def claim(sessao: Session, laboratorio_id: uuid.UUID, expedicao_id: uuid.UUID) -> ExpedicaoClaimLer:
    """`POST /expeditions/{id}/claim` (ADR-006): o coracao da Fase 7.

    Transacao unica, na ordem exigida pelo plano:

      1. `SELECT ... FOR UPDATE` na expedicao.
      2. Ja concluida (sucesso ou falha): devolve o relatorio GRAVADO, sem
         escrever nada (idempotencia, criterios 4 e 5).
      3. Prazo nao vencido: recusa com `EXPEDICAO_EM_CURSO`.
      4. Abortada: recusa com `EXPEDICAO_ABORTADA`.
      5. Senao (aguardando relatorio): resolve, grava tudo, devolve.

    O status terminal e checado ANTES do prazo e do aborto, e nao na ordem
    literal "coluna != EM_CURSO -> devolve": uma expedicao abortada ANTES do
    `eta` original (abortar so e permitido enquanto ainda EM_CURSO) teria
    `agora < eta` verdadeiro, e checar o prazo primeiro devolveria
    `EXPEDICAO_EM_CURSO` para uma missao que ja foi cancelada — o professor
    levaria um erro que nao descreve o que aconteceu.
    """
    agora = datetime.now(UTC)

    expedicao = expedicoes_repo.travar_para_resolver(sessao, laboratorio_id, expedicao_id)
    if expedicao is None:
        raise RecursoNaoEncontrado()

    status = expedition.status_de_expedicao(expedicao.status)

    if status in (
        expedition.StatusExpedicao.CONCLUIDA_SUCESSO,
        expedition.StatusExpedicao.CONCLUIDA_FALHA,
    ):
        sessao.rollback()
        return _resposta_do_claim(sessao, laboratorio_id, expedicao_id, agora)

    if status is expedition.StatusExpedicao.ABORTADA:
        sessao.rollback()
        raise ExpedicaoAbortada()

    if agora < expedicao.eta:
        sessao.rollback()
        raise ExpedicaoEmCurso()

    # So resta `EM_CURSO` com o `eta` ja vencido: AGUARDANDO_RELATORIO.
    treinador = treinadores_repo.travar_treinador_com_time(
        sessao, laboratorio_id, expedicao.treinador_id
    )
    if treinador is None:  # pragma: no cover - FK garante a existencia
        raise RecursoNaoEncontrado()

    contexto = _montar_contexto(sessao, expedicao, treinador)
    relatorio = expedition.resolver(contexto, random.Random(expedicao.seed))

    _gravar_resultado(sessao, expedicao, treinador, relatorio, agora=agora)
    sessao.commit()

    return _resposta_do_claim(sessao, laboratorio_id, expedicao_id, agora)
