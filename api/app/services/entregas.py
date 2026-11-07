"""Caso de uso da Central de Entregas (spec 008, SDD 4.9).

A fronteira do Artigo I entra aqui com forca total: este servico le o
relogio, cria o gerador aleatorio (Artigo III — sem seed gravado, porque o
pedido e persistido de imediato, nunca "resolvido" depois a partir de uma
semente), trava linhas em ordem deterministica (Artigo VII) e traduz tudo
para o vocabulario de `app.game.delivery`. Nenhuma regra de jogo mora aqui.

Quatro operacoes, cada uma com seu proprio risco de concorrencia:

  `listar`   — so leitura, nunca gera nem regenera nada (regra da spec 008:
              "a reposicao acontece no POST /deliveries/refresh, nunca numa
              leitura").
  `refresh`  — as DUAS semanticas da mesma rota (plan.md): preenche vagas
              abertas por expiracao/aceite sem tocar no relogio do
              intervalo, ou descarta a lista inteira e exige o intervalo.
  `aceitar`  — transacao unica, travando em ordem deterministica: a entrega,
              os Pokemon escolhidos, o treinador, e o laboratorio por ultimo
              (plan.md, secao 13; ordem canonica — ver `pokemon_service.soltar`).
  `claim`    — a primeira operacao DESTRUTIVA do jogo (plan.md, secao 14):
              mesmo padrao do ADR-006, `SELECT ... FOR UPDATE` + checagem de
              status + segunda chamada que releem sem escrever.

Ordem de lock canonica do projeto (Artigo VII): Pokemon antes do treinador,
laboratorio sempre por ultimo quando a operacao precisa dele; entrega (ou
qualquer outro recurso que nao seja Pokemon/treinador/laboratorio) trava
antes do laboratorio tambem — e o que `refresh` faz ao travar as entregas que
vai descartar ANTES do laboratorio. A justificativa completa mora no
docstring de `pokemon_service.soltar`.
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.erros import (
    AguardeParaRegerar,
    ConflitoDeEntrega,
    ConflitoDeSoltura,
    EntregaEmCurso,
    EntregaExpirada,
    EntregaNaoDisponivel,
    PokemonIndisponivel,
    RecursoNaoEncontrado,
    TreinadorOcupadoParaEntrega,
)
from app.game import balance, delivery
from app.game import laboratorio as laboratorio_dominio
from app.game import mapa as mapa_dominio
from app.game import soltar as soltar_dominio
from app.game import trainers as trainers_dominio
from app.game.expedition import tempo_restante
from app.game.mapa import GrafoDeLocais
from app.game.trainers import StatusTreinador
from app.models import Entrega, Local, PokemonInstancia
from app.repositories import entregas as entregas_repo
from app.repositories import especies as especies_repo
from app.repositories import laboratorios as laboratorios_repo
from app.repositories import mapa as mapa_repo
from app.repositories import pokemon as pokemon_repo
from app.repositories import treinadores as treinadores_repo
from app.schemas.deliveries import (
    EntregaClaimLer,
    EntregaLer,
    GanhoDeExperienciaLer,
    ListaEntregas,
    PokemonEntregueLer,
    RequisitoLer,
    ResultadoDeEntregaLer,
)

# --- Traducao ORM -> dominio (fronteira do Artigo I) ------------------------


def _grafo_de_locais(locais: Sequence[Local]) -> GrafoDeLocais:
    """Traduz os `Local` do ORM para o grafo que `game.mapa` entende.

    Mesma funcao de `services/expedicoes.py` e `services/mapa.py`, duplicada
    aqui pelo mesmo motivo que elas se duplicam entre si: importar um helper
    privado de outro `services/` acopla os dois a um detalhe de implementacao
    que nenhum promete manter.
    """
    return mapa_dominio.montar_grafo(
        mapa_dominio.LocalNoGrafo(
            id=local.id,
            custo_travessia_minutos=local.custo_travessia_minutos,
            encontros_base=local.encontros_base,
            vizinhos=tuple(local.vizinhos),
        )
        for local in locais
    )


def _custo_viagem_ate(grafo: GrafoDeLocais, destino_id: str) -> int:
    """A distancia de IDA do laboratorio (Pallet Town) ate a cidade destino.

    SDD 4.9: "a entrega parte sempre do laboratorio, porque e la que os
    Pokemon estao" — origem FIXA, diferente da expedicao (que parte do local
    visitado mais proximo). `rota_ate` com um unico visitado e exatamente essa
    busca de origem unica, reaproveitando o mesmo Dijkstra de `game.mapa`.
    """
    rota = mapa_dominio.rota_ate(grafo, {balance.LOCAL_INICIAL_ID}, destino_id)
    if rota is None:  # pragma: no cover - toda cidade de destino nasce alcancavel do laboratorio
        raise RecursoNaoEncontrado()
    return rota.custo_viagem_minutos


def _especies_para_entrega(sessao: Session) -> tuple[delivery.EspecieParaEntrega, ...]:
    """O catalogo inteiro, com os locais onde cada especie aparece.

    A Pokedex do laboratorio NAO entra aqui (SDD 4.9): e a mesma tabela de
    referencia para qualquer professor, so com o nome, a taxa de captura e os
    locais de encontro.
    """
    especies = especies_repo.listar_todas(sessao)
    encontros = mapa_repo.listar_todos_os_encontros(sessao)
    locais_por_especie: dict[int, set[str]] = {}
    for linha in encontros:
        locais_por_especie.setdefault(linha.especie_id, set()).add(linha.local_id)
    return tuple(
        delivery.EspecieParaEntrega(
            id=especie.id,
            nome=especie.nome,
            taxa_captura=especie.taxa_captura,
            locais_ids=tuple(sorted(locais_por_especie.get(especie.id, ()))),
        )
        for especie in especies
    )


def _cidades_desbloqueadas(
    locais_por_id: dict[str, Local], visitados: set[str]
) -> tuple[delivery.CidadeDeDestino, ...]:
    """As cidades ja abertas para este laboratorio (invariante 16).

    A ordem nao importa: `game.delivery.gerar_pedido` ordena por id antes de
    sortear (ordem canonica imposta la, nao confiada ao chamador).
    """
    return tuple(
        delivery.CidadeDeDestino(id=local.id, nome=local.nome)
        for local_id, local in locais_por_id.items()
        if local.tipo == "CIDADE" and local_id in visitados
    )


def _agrupar_livres(viveiro: Sequence[PokemonInstancia]) -> dict[int, list[PokemonInstancia]]:
    """Os Pokemon do viveiro que NAO estao comprometidos, por especie.

    Ordenados por `(nivel, id)` crescente: e a mesma preferencia que alimenta
    a previa de recompensa abaixo (o professor que aceita um pedido de dois
    Pidgey entre quatro, tipicamente, prefere mandar os de nivel mais baixo e
    guardar o resto para o time) e o calculo de `disponiveis_no_viveiro`.
    """
    livres: dict[int, list[PokemonInstancia]] = {}
    for pokemon in viveiro:
        if pokemon.comprometido_entrega_id is not None:
            continue
        livres.setdefault(pokemon.especie_id, []).append(pokemon)
    for lista in livres.values():
        lista.sort(key=lambda p: (p.nivel, p.id))
    return livres


def _contexto_partilhado(
    sessao: Session, laboratorio_id: uuid.UUID
) -> tuple[GrafoDeLocais, dict[int, list[PokemonInstancia]], bool, int]:
    """O que toda ficha de entrega precisa e que NAO muda entre entregas de
    uma mesma leitura: o grafo (para a distancia ate o destino), o estoque
    livre do viveiro por especie, se ha algum treinador disponivel agora, e
    quantos Pokemon o laboratorio tem para sobrar (`pokemon_repo.contar`,
    ja excluindo quem esta comprometido com OUTRA entrega) — usado para que
    `atendivel` nao prometa um aceite que `soltar_dominio.
    exigir_que_sobre_pokemon` recusaria (achado da revisao da Fase 8)."""
    grafo = _grafo_de_locais(mapa_repo.listar_locais(sessao))
    livres_por_especie = _agrupar_livres(pokemon_repo.listar_viveiro(sessao, laboratorio_id))
    treinadores = treinadores_repo.listar(sessao, laboratorio_id)
    algum_treinador_disponivel = any(
        trainers_dominio.status_de(treinador.status) is StatusTreinador.DISPONIVEL
        for treinador in treinadores
    )
    total_do_laboratorio = pokemon_repo.contar(sessao, laboratorio_id)
    return grafo, livres_por_especie, algum_treinador_disponivel, total_do_laboratorio


_MOTIVO_POR_ESTADO: dict[delivery.EstadoObservadoEntrega, str] = {
    delivery.EstadoObservadoEntrega.EXPIRADA: "Este pedido venceu e saiu de circulacao.",
    delivery.EstadoObservadoEntrega.EM_CURSO: "Este pedido ja foi aceito e esta a caminho.",
    delivery.EstadoObservadoEntrega.CONCLUIDA: "Este pedido ja foi concluido.",
    delivery.EstadoObservadoEntrega.DESCARTADA: "Este pedido foi descartado.",
}


def _montar_entrega_ler(
    entrega: Entrega,
    *,
    agora: datetime,
    escala: float,
    grafo: GrafoDeLocais,
    livres_por_especie: dict[int, list[PokemonInstancia]],
    algum_treinador_disponivel: bool,
    total_do_laboratorio: int,
) -> EntregaLer:
    """A ficha de UMA entrega (plan.md, contratos de API).

    `atendivel`/`motivo` combina quatro fatos que o professor precisa ver
    juntos: estado, estoque do viveiro, corpo de treinadores, e se mandar
    este pedido deixaria o laboratorio vazio (invariante 25) — este ultimo
    chama `game.soltar.exigir_que_sobre_pokemon` de verdade, a MESMA funcao
    que `aceitar` usa sob lock, para que a ficha nunca prometa um aceite que
    o botao recusa (achado da revisao da Fase 8: "atendivel promete o que o
    aceite recusa", mesma familia de defeito da previa de despacho). E um
    instantaneo, nao uma reserva: aceitar sob lock pode descobrir um estoque
    diferente do que esta tela mostrou ha um segundo, e e por isso que o
    aceite reconfere tudo de novo (regra 20 da spec 008).
    """
    estado = delivery.estado_observado_entrega(
        entrega.status, entrega.expira_em, entrega.eta, agora
    )

    disponivel = estado is delivery.EstadoObservadoEntrega.DISPONIVEL
    atendivel = disponivel
    motivo: str | None = None
    entregues_preview: list[delivery.PokemonEntregue] = []

    requisitos_ler: list[RequisitoLer] = []
    for requisito in entrega.requisitos:
        candidatos = livres_por_especie.get(requisito.especie_id, [])
        requisitos_ler.append(
            RequisitoLer(
                especie_id=requisito.especie_id,
                especie_nome=requisito.especie.nome,
                quantidade=requisito.quantidade,
                disponiveis_no_viveiro=len(candidatos),
            )
        )
        if disponivel and atendivel:
            if len(candidatos) < requisito.quantidade:
                atendivel = False
                motivo = "Faltam Pokemon no viveiro para este pedido."
            else:
                entregues_preview.extend(
                    delivery.PokemonEntregue(
                        especie_nome=requisito.especie.nome, nivel=pokemon.nivel
                    )
                    for pokemon in candidatos[: requisito.quantidade]
                )

    if disponivel and atendivel:
        try:
            soltar_dominio.exigir_que_sobre_pokemon(
                total_do_laboratorio, saindo=len(entregues_preview)
            )
        except soltar_dominio.ErroDeSoltura as erro:
            atendivel = False
            motivo = str(erro)

    if disponivel and atendivel and not algum_treinador_disponivel:
        atendivel = False
        motivo = "Nenhum treinador disponivel para esta entrega."
    if not atendivel and motivo is None:
        motivo = _MOTIVO_POR_ESTADO.get(estado)

    segundos_para_expirar: int | None = None
    duracao_minutos = entrega.duracao_minutos
    recompensa_moedas = entrega.recompensa_moedas
    recompensa_exp_laboratorio = entrega.recompensa_exp_laboratorio
    recompensa_exp_treinador = entrega.recompensa_exp_treinador
    segundos_restantes: int | None = None
    eta = entrega.eta

    if disponivel:
        segundos_para_expirar = delivery.segundos_para_expirar(entrega.expira_em, agora)
        custo = _custo_viagem_ate(grafo, entrega.local_destino_id)
        # Preview: sem treinador escolhido ainda, a duracao base (sem desconto
        # de nivel) e a recompensa estimada com os candidatos mais baratos de
        # manter em time (os de nivel mais baixo) que atendem hoje. O valor
        # REAL nasce no aceite e nunca muda depois (ver `marcar_aceita`).
        duracao_minutos = delivery.duracao_da_entrega(
            custo_viagem_minutos=custo, nivel_treinador=None, escala=escala
        )
        if entregues_preview:
            recompensa = delivery.recompensa_da_entrega(
                entregues_preview, custo_viagem_minutos=custo
            )
            recompensa_moedas = recompensa.moedas
            recompensa_exp_laboratorio = recompensa.exp_laboratorio
            recompensa_exp_treinador = recompensa.exp_treinador
        else:
            recompensa_moedas = recompensa_exp_laboratorio = recompensa_exp_treinador = None
        eta = None
    elif estado is delivery.EstadoObservadoEntrega.EM_CURSO:
        segundos_restantes = tempo_restante(entrega.eta, agora) if entrega.eta else None

    return EntregaLer(
        id=entrega.id,
        titulo=entrega.titulo,
        local_destino_id=entrega.local_destino_id,
        local_destino_nome=entrega.local_destino.nome,
        estado_observado=estado.value,
        segundos_para_expirar=segundos_para_expirar,
        requisitos=requisitos_ler,
        atendivel=atendivel,
        motivo=motivo,
        duracao_minutos=duracao_minutos,
        recompensa_moedas=recompensa_moedas,
        recompensa_exp_laboratorio=recompensa_exp_laboratorio,
        recompensa_exp_treinador=recompensa_exp_treinador,
        treinador_id=entrega.treinador_id,
        eta=eta,
        segundos_restantes=segundos_restantes,
    )


# --- Leitura (criterios 18 e 22) ---------------------------------------------


def listar(sessao: Session, laboratorio_id: uuid.UUID) -> ListaEntregas:
    """`GET /deliveries`: nunca gera nem regenera nada (so `refresh` escreve)."""
    agora = datetime.now(UTC)
    escala = get_settings().expedition_time_scale

    laboratorio = laboratorios_repo.buscar_por_id(sessao, laboratorio_id)
    if laboratorio is None:  # pragma: no cover - todo professor tem laboratorio
        raise RecursoNaoEncontrado()

    entregas = entregas_repo.listar(sessao, laboratorio_id)
    grafo, livres_por_especie, algum_treinador_disponivel, total_do_laboratorio = (
        _contexto_partilhado(sessao, laboratorio_id)
    )
    items = [
        _montar_entrega_ler(
            entrega,
            agora=agora,
            escala=escala,
            grafo=grafo,
            livres_por_especie=livres_por_especie,
            algum_treinador_disponivel=algum_treinador_disponivel,
            total_do_laboratorio=total_do_laboratorio,
        )
        for entrega in entregas
    ]
    estados = [
        delivery.estado_observado_entrega(entrega.status, entrega.expira_em, entrega.eta, agora)
        for entrega in entregas
    ]
    return ListaEntregas(
        items=items,
        vagas_para_repor=delivery.vagas_para_repor(estados),
        segundos_para_regerar=delivery.segundos_para_regerar(
            laboratorio.entregas_geradas_em, agora, escala
        ),
    )


# --- Reposicao e regeracao (tarefa 12, invariantes 15, 18, 19 e 23) ----------


def refresh(sessao: Session, laboratorio_id: uuid.UUID) -> ListaEntregas:
    """`POST /deliveries/refresh`: as DUAS semanticas da mesma rota (plan.md).

    vagas = ENTREGAS_DISPONIVEIS - pedidos validos e nao expirados
    vagas > 0  -> preenche as vagas, SEM tocar no relogio do intervalo
    vagas == 0 -> e descarte da lista valida -> exige o intervalo

    Ordem de lock (Artigo VII, ordem canonica do projeto — ver
    `pokemon_service.soltar`): o laboratorio e travado por ULTIMO. As
    entregas que o descarte vai escrever (`marcar_descartadas`) sao travadas
    ANTES dele, na mesma ordem de `aceitar` (entrega antes do laboratorio).
    Invertida, um `refresh` descartando e um `aceitar` concorrente sobre o
    MESMO pedido deadlockariam: um trava laboratorio-depois-entrega, o outro
    entrega-depois-laboratorio (revisao da Fase 8, achado "dois deadlocks").

    A leitura de `entregas`/`estados` abaixo, ANTES de qualquer lock, so
    decide qual dos dois caminhos seguir — e sujeita a corrida, mas e so uma
    estimativa: o caminho do descarte revalida sob lock quais pedidos
    CONTINUAM `DISPONIVEL` antes de escrever `DESCARTADA` por cima deles (uma
    entrega pode ter sido aceita por outra transacao entre a leitura e o
    lock), e o caminho da reposicao nao precisa de revalidacao porque so
    insere linhas novas, que nenhuma outra transacao pode disputar.
    """
    agora = datetime.now(UTC)
    escala = get_settings().expedition_time_scale

    entregas = entregas_repo.listar(sessao, laboratorio_id)
    estados = [
        delivery.estado_observado_entrega(entrega.status, entrega.expira_em, entrega.eta, agora)
        for entrega in entregas
    ]
    vagas = delivery.vagas_para_repor(estados)

    if vagas == 0:
        candidatos_ids = [
            entrega.id
            for entrega, estado in zip(entregas, estados, strict=True)
            if estado is delivery.EstadoObservadoEntrega.DISPONIVEL
        ]
        travadas = entregas_repo.travar_varias(sessao, laboratorio_id, candidatos_ids)

        laboratorio = laboratorios_repo.travar(sessao, laboratorio_id)
        if laboratorio is None:  # pragma: no cover
            sessao.rollback()
            raise RecursoNaoEncontrado()

        espera = delivery.segundos_para_regerar(laboratorio.entregas_geradas_em, agora, escala)
        if espera > 0:
            sessao.rollback()
            raise AguardeParaRegerar(detalhes={"segundos_para_regerar": espera})

        # Revalidacao sob lock: entre a leitura sem trava acima e este lock,
        # uma destas entregas pode ter sido aceita por outra transacao — ela
        # deixou de ser DISPONIVEL e nao pode ser descartada por cima do
        # aceite de alguem (mesmo raciocinio do `pokemon_repo.contar`
        # corrigido nesta revisao: nunca decidir com um instantaneo velho).
        ainda_validas = [
            entrega
            for entrega in travadas
            if delivery.estado_observado_entrega(
                entrega.status, entrega.expira_em, entrega.eta, agora
            )
            is delivery.EstadoObservadoEntrega.DISPONIVEL
        ]
        entregas_repo.marcar_descartadas(sessao, ainda_validas)
        laboratorios_repo.atualizar_sorteio_entregas(laboratorio, agora)
        quantidade = balance.ENTREGAS_DISPONIVEIS
    else:
        laboratorio = laboratorios_repo.travar(sessao, laboratorio_id)
        if laboratorio is None:  # pragma: no cover
            sessao.rollback()
            raise RecursoNaoEncontrado()
        quantidade = vagas
        # Reposicao tambem e sorteio de verdade (`game.delivery.gerar_pedidos`
        # roda igual, so que para menos pedidos), e o intervalo conta "desde
        # o ultimo sorteio" (regra 19) — nao so desde o ultimo descarte. Sem
        # este carimbo, reposicoes gota a gota nunca avancam o relogio, e uma
        # lista que acabou de ser completada por reposicao fica livre para um
        # descarte IMEDIATO e gratuito logo em seguida (achado da revisao da
        # Fase 8: "repor libera uma regeracao gratuita"). So carimba quando
        # JA havia um sorteio anterior: o bootstrap (lista vazia, criterio
        # 13, `entregas_geradas_em` ainda nulo) continua sem carimbo, para a
        # PROXIMA chamada — que descarta essa lista recem-cheia, criterio 21
        # — continuar livre tambem (ver docstring de `atualizar_sorteio_
        # entregas`). Carimbar aqui NAO faz a propria reposicao esperar
        # (invariante 18): a condicao abaixo so GRAVA, nunca BLOQUEIA.
        if laboratorio.entregas_geradas_em is not None:
            laboratorios_repo.atualizar_sorteio_entregas(laboratorio, agora)

    if quantidade > 0:
        locais = mapa_repo.listar_locais(sessao)
        locais_por_id = {local.id: local for local in locais}
        grafo = _grafo_de_locais(locais)
        visitados = mapa_repo.listar_visitados(sessao, laboratorio_id)
        especies = _especies_para_entrega(sessao)
        cidades = _cidades_desbloqueadas(locais_por_id, visitados)

        try:
            pedidos = delivery.gerar_pedidos(
                quantidade,
                nivel_laboratorio=laboratorio.nivel,
                especies=especies,
                grafo=grafo,
                visitados=visitados,
                cidades=cidades,
                gerador=random.Random(),
            )
        except delivery.ErroDeEntrega as erro:
            sessao.rollback()
            raise ConflitoDeEntrega(erro) from erro

        expira_em = delivery.expiracao_da_oferta(agora, escala)
        entregas_repo.criar_pedidos(
            sessao,
            laboratorio_id=laboratorio_id,
            pedidos=pedidos,
            gerada_em=agora,
            expira_em=expira_em,
        )

    sessao.commit()
    return listar(sessao, laboratorio_id)


# --- Aceite (tarefa 13, criterios 20 e 23 a 26) -------------------------------


def aceitar(
    sessao: Session,
    laboratorio_id: uuid.UUID,
    entrega_id: uuid.UUID,
    treinador_id: uuid.UUID,
    pokemon_ids: Sequence[uuid.UUID],
) -> EntregaLer:
    """`POST /deliveries/{id}/accept`: travando em ordem deterministica.

    Ordem de lock (Artigo VII, ordem canonica do projeto inteiro — ver
    `pokemon_service.soltar`): a entrega primeiro (recurso proprio desta
    rota, sem conflito com nenhum outro caminho), depois os Pokemon
    escolhidos (ordenados por id, `pokemon_repo.travar_varios`), depois o
    treinador, e o laboratorio por ultimo. Pokemon antes do treinador, nunca
    o contrario: `trainers_service.definir_time` e `pokemon_service.soltar`
    travam na mesma ordem, e invertida aqui um `PUT /trainers/{id}/team` e
    este aceite, disputando o mesmo par (Pokemon de um time, treinador dele),
    travariam em ordens opostas — deadlock classico.
    """
    agora = datetime.now(UTC)
    escala = get_settings().expedition_time_scale

    entrega = entregas_repo.travar_para_aceitar(sessao, laboratorio_id, entrega_id)
    if entrega is None:
        raise RecursoNaoEncontrado()

    estado = delivery.estado_observado_entrega(
        entrega.status, entrega.expira_em, entrega.eta, agora
    )
    if estado is delivery.EstadoObservadoEntrega.EXPIRADA:
        sessao.rollback()
        raise EntregaExpirada()
    if not estado.aceitavel:
        sessao.rollback()
        raise EntregaNaoDisponivel()

    ids_unicos = sorted(set(pokemon_ids))
    if len(ids_unicos) != len(pokemon_ids) or not ids_unicos:
        sessao.rollback()
        raise PokemonIndisponivel("Escolha ao menos um Pokemon, sem repetir nenhum.", detalhes={})

    escolhidos = pokemon_repo.travar_varios(sessao, laboratorio_id, ids_unicos)
    if len(escolhidos) != len(ids_unicos):
        sessao.rollback()
        raise PokemonIndisponivel()
    for pokemon in escolhidos:
        if pokemon.treinador_id is not None or pokemon.comprometido_entrega_id is not None:
            sessao.rollback()
            raise PokemonIndisponivel(detalhes={"pokemon_id": str(pokemon.id)})

    treinador = treinadores_repo.travar_treinador(sessao, laboratorio_id, treinador_id)
    if treinador is None:
        sessao.rollback()
        raise RecursoNaoEncontrado()
    if trainers_dominio.status_de(treinador.status) is not StatusTreinador.DISPONIVEL:
        sessao.rollback()
        raise TreinadorOcupadoParaEntrega()

    requisitos = entregas_repo.buscar_requisitos(sessao, entrega.id)
    try:
        delivery.exigir_pokemon_que_atendem(
            [
                delivery.RequisitoDoPedido(
                    especie_id=requisito.especie_id,
                    especie_nome=requisito.especie.nome,
                    quantidade=requisito.quantidade,
                )
                for requisito in requisitos
            ],
            [pokemon.especie_id for pokemon in escolhidos],
        )
    except delivery.PokemonNaoAtendeAoPedido as erro:
        sessao.rollback()
        raise ConflitoDeEntrega(erro) from erro

    laboratorio = laboratorios_repo.travar(sessao, laboratorio_id)
    if laboratorio is None:  # pragma: no cover
        sessao.rollback()
        raise RecursoNaoEncontrado()
    total_do_laboratorio = pokemon_repo.contar(sessao, laboratorio_id)
    try:
        soltar_dominio.exigir_que_sobre_pokemon(total_do_laboratorio, saindo=len(escolhidos))
    except soltar_dominio.ErroDeSoltura as erro:
        sessao.rollback()
        raise ConflitoDeSoltura(erro) from erro

    grafo = _grafo_de_locais(mapa_repo.listar_locais(sessao))
    custo = _custo_viagem_ate(grafo, entrega.local_destino_id)
    duracao_minutos = delivery.duracao_da_entrega(
        custo_viagem_minutos=custo, nivel_treinador=treinador.nivel, escala=escala
    )
    catalogo = especies_repo.buscar_catalogo(sessao, {pokemon.especie_id for pokemon in escolhidos})
    entregues = [
        delivery.PokemonEntregue(
            especie_nome=catalogo[pokemon.especie_id].nome, nivel=pokemon.nivel
        )
        for pokemon in escolhidos
    ]
    recompensa = delivery.recompensa_da_entrega(entregues, custo_viagem_minutos=custo)
    eta = agora + timedelta(minutes=duracao_minutos)

    for pokemon in escolhidos:
        pokemon_repo.comprometer(pokemon, entrega.id)
    treinadores_repo.despachar_para_entrega(treinador)
    entregas_repo.marcar_aceita(
        entrega,
        treinador_id=treinador.id,
        started_at=agora,
        eta=eta,
        duracao_minutos=duracao_minutos,
        recompensa_moedas=recompensa.moedas,
        recompensa_exp_laboratorio=recompensa.exp_laboratorio,
        recompensa_exp_treinador=recompensa.exp_treinador,
    )
    sessao.commit()

    return _buscar_e_montar(sessao, laboratorio_id, entrega_id)


def _buscar_e_montar(
    sessao: Session, laboratorio_id: uuid.UUID, entrega_id: uuid.UUID
) -> EntregaLer:
    agora = datetime.now(UTC)
    escala = get_settings().expedition_time_scale
    atualizada = entregas_repo.buscar_detalhe(sessao, laboratorio_id, entrega_id)
    if atualizada is None:  # pragma: no cover - acabamos de gravar
        raise RecursoNaoEncontrado()
    grafo, livres_por_especie, algum_treinador_disponivel, total_do_laboratorio = (
        _contexto_partilhado(sessao, laboratorio_id)
    )
    return _montar_entrega_ler(
        atualizada,
        agora=agora,
        escala=escala,
        grafo=grafo,
        livres_por_especie=livres_por_especie,
        algum_treinador_disponivel=algum_treinador_disponivel,
        total_do_laboratorio=total_do_laboratorio,
    )


# --- Conclusao (tarefa 14, ADR-006, criterios 27 a 30) -----------------------


def claim(sessao: Session, laboratorio_id: uuid.UUID, entrega_id: uuid.UUID) -> EntregaClaimLer:
    """`POST /deliveries/{id}/claim`: mesmo padrao do ADR-006.

    E a primeira operacao DESTRUTIVA do jogo (plan.md): na expedicao, resolver
    duas vezes duplicaria ganho; aqui apagaria Pokemon que nao deviam sair, e
    isso e irreparavel. `SELECT ... FOR UPDATE`, checagem de status DEPOIS do
    lock, segunda chamada devolve o resultado gravado sem escrever.

    **Nao reconfere o invariante 25 aqui, de proposito.** O `aceite` ja
    aprovou esta remocao especifica contra `pokemon_repo.contar` — que, apos
    a correcao do achado critico da Fase 8, exclui TODOS os Pokemon ja
    comprometidos (com qualquer entrega, nao so esta) da contagem de quem
    "fica". Isso significa que o aceite ja considerou estes Pokemon como
    partidos no momento em que aprovou a saida. Nenhuma operacao entre o
    aceite e este `claim` pode reduzir essa margem: `soltar` usa a MESMA
    `contar` (exclui comprometidos, inclusive os desta entrega) antes de
    cada remocao, entao ele nunca deixa o laboratorio num estado em que
    concluir esta entrega zeraria o acervo — se deixasse, o PROPRIO `soltar`
    que causou isso ja teria sido recusado. Reconferir aqui seria repetir uma
    conta que so pode dar o mesmo resultado, e os Pokemon comprometidos desta
    entrega sao intocaveis por qualquer outro caminho (nao entram em time,
    expedicao nem outra entrega — invariante 22) entre os dois momentos.
    """
    agora = datetime.now(UTC)

    entrega = entregas_repo.travar_para_resolver(sessao, laboratorio_id, entrega_id)
    if entrega is None:
        raise RecursoNaoEncontrado()

    status = delivery.status_de_entrega(entrega.status)

    if status is delivery.StatusEntrega.CONCLUIDA:
        sessao.rollback()
        return _resposta_do_claim(sessao, laboratorio_id, entrega_id)

    if status is not delivery.StatusEntrega.EM_CURSO:
        # DISPONIVEL ou DESCARTADA: nunca foi aceita, nao ha o que concluir.
        sessao.rollback()
        raise EntregaNaoDisponivel()

    if (
        entrega.eta is None or entrega.treinador_id is None
    ):  # pragma: no cover - marcar_aceita grava os dois
        sessao.rollback()
        raise RecursoNaoEncontrado()
    if agora < entrega.eta:
        sessao.rollback()
        raise EntregaEmCurso()

    # Ordem de lock (Artigo VII, ordem canonica do projeto — ver
    # `pokemon_service.soltar`): Pokemon antes do treinador, laboratorio por
    # ultimo. Mesma ordem de `aceitar`, nunca o contrario.
    pokemon_comprometidos = pokemon_repo.listar_comprometidos(sessao, laboratorio_id, entrega.id)
    catalogo = especies_repo.buscar_catalogo(
        sessao, {pokemon.especie_id for pokemon in pokemon_comprometidos}
    )
    pokemon_entregues = [
        PokemonEntregueLer(especie_nome=catalogo[pokemon.especie_id].nome, nivel=pokemon.nivel)
        for pokemon in pokemon_comprometidos
    ]

    treinador = treinadores_repo.travar_treinador(sessao, laboratorio_id, entrega.treinador_id)
    if treinador is None:  # pragma: no cover - FK garante a existencia
        sessao.rollback()
        raise RecursoNaoEncontrado()

    laboratorio = laboratorios_repo.travar(sessao, laboratorio_id)
    if laboratorio is None:  # pragma: no cover
        raise RecursoNaoEncontrado()

    nivel_lab_antes = laboratorio.nivel
    exp_laboratorio = laboratorio.experiencia + (entrega.recompensa_exp_laboratorio or 0)
    nivel_lab_depois = laboratorio_dominio.nivel_para_experiencia(exp_laboratorio)
    laboratorios_repo.atualizar_progressao(
        laboratorio, nivel=nivel_lab_depois, experiencia=exp_laboratorio
    )
    laboratorios_repo.creditar_moedas(laboratorio, entrega.recompensa_moedas or 0)

    nivel_treinador_antes = treinador.nivel
    exp_treinador = treinador.experiencia + (entrega.recompensa_exp_treinador or 0)
    nivel_treinador_depois = trainers_dominio.nivel_para_experiencia(exp_treinador)
    treinadores_repo.concluir_entrega(
        treinador, nivel=nivel_treinador_depois, experiencia=exp_treinador
    )

    for pokemon in pokemon_comprometidos:
        pokemon_repo.excluir(sessao, pokemon)

    resumo = {
        "pokemon_entregues": [item.model_dump() for item in pokemon_entregues],
        "laboratorio": {
            "nivel_antes": nivel_lab_antes,
            "nivel_depois": nivel_lab_depois,
            "exp_ganha": entrega.recompensa_exp_laboratorio or 0,
        },
        "treinador": {
            "nivel_antes": nivel_treinador_antes,
            "nivel_depois": nivel_treinador_depois,
            "exp_ganha": entrega.recompensa_exp_treinador or 0,
        },
        "lugares_liberados": len(pokemon_comprometidos),
        # O saldo de moedas LOGO APOS este credito (achado da revisao da
        # Fase 8: "segunda chamada do claim devolve corpo diferente"). Gravado
        # aqui, e nao relido de `laboratorio.moedas` em `_resposta_do_claim`,
        # porque o saldo ATUAL muda com qualquer expedicao ou entrega
        # concluida depois desta — o plan.md promete que a segunda chamada
        # devolve O MESMO corpo, e isso so e verdade lendo o que foi GRAVADO,
        # mesmo raciocinio do resto deste `resumo`.
        "moedas_total": laboratorio.moedas,
    }
    entregas_repo.marcar_concluida(entrega, resolvida_em=agora, resultado_resumo=resumo)
    sessao.commit()

    return _resposta_do_claim(sessao, laboratorio_id, entrega_id)


def _resposta_do_claim(
    sessao: Session, laboratorio_id: uuid.UUID, entrega_id: uuid.UUID
) -> EntregaClaimLer:
    """Reconstroi a resposta do que ja esta GRAVADO — nunca reexecuta o claim.

    Mesmo raciocinio de `expedicoes_service._montar_relatorio_ler` (ADR-006):
    `resultado_resumo` e a verdade, porque os Pokemon entregues ja nao existem
    mais para serem relidos, e o nivel de laboratorio/treinador "antes desta
    entrega" muda a cada expedicao ou entrega concluida depois desta.
    """
    atualizada = entregas_repo.buscar_detalhe(sessao, laboratorio_id, entrega_id)
    if atualizada is None:  # pragma: no cover
        raise RecursoNaoEncontrado()
    resumo = atualizada.resultado_resumo
    if resumo is None:  # pragma: no cover - so chega aqui ja concluida
        raise RecursoNaoEncontrado()

    agora = datetime.now(UTC)
    escala = get_settings().expedition_time_scale
    grafo, livres_por_especie, algum_treinador_disponivel, total_do_laboratorio = (
        _contexto_partilhado(sessao, laboratorio_id)
    )
    entrega_ler = _montar_entrega_ler(
        atualizada,
        agora=agora,
        escala=escala,
        grafo=grafo,
        livres_por_especie=livres_por_especie,
        algum_treinador_disponivel=algum_treinador_disponivel,
        total_do_laboratorio=total_do_laboratorio,
    )
    resultado = ResultadoDeEntregaLer(
        pokemon_entregues=[PokemonEntregueLer(**item) for item in resumo["pokemon_entregues"]],
        moedas_ganhas=atualizada.recompensa_moedas or 0,
        # Gravado no resumo pelo proprio `claim`, nunca relido do saldo ATUAL
        # (achado da revisao da Fase 8): o saldo muda com qualquer entrega ou
        # expedicao concluida depois desta, e a segunda chamada precisa
        # devolver O MESMO corpo que a primeira (plan.md).
        moedas_total=resumo["moedas_total"],
        laboratorio=GanhoDeExperienciaLer(**resumo["laboratorio"]),
        treinador=GanhoDeExperienciaLer(**resumo["treinador"]),
        lugares_liberados=resumo["lugares_liberados"],
    )
    return EntregaClaimLer(entrega=entrega_ler, resultado=resultado)
