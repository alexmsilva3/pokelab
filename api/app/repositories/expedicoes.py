"""Acesso a tabela `expedicoes` e a carga que cada uma levou (spec 006).

`GET /expeditions` precisa de treinador, local de destino, local de origem e
carga numa unica leitura — "cuidado com N+1" (plan.md, secao 6). `joinedload`
resolve os quatro escalares (treinador e os dois locais) na mesma consulta;
`selectinload` busca a carga numa segunda consulta, por tabela, e nao uma por
expedicao.

A escrita do despacho trava duas coisas na mesma transacao (Artigo VII,
plan.md secao 5): a linha do treinador — isso mora em
`treinadores_repo.travar_treinador_com_time` — e as linhas de `item_estoques`
da carga, em `itens_repo.travar_quantidades`. Este modulo so grava a
expedicao em si depois que as duas travas e a validacao de dominio ja
passaram.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session, joinedload, selectinload

from app.game.expedition import DespachoCalculado, EventoDeCampo, ItemDoRelatorio
from app.models import Expedicao, ExpedicaoEvento, ExpedicaoItem


def _relacoes_base(consulta: Select) -> Select:
    return consulta.options(
        joinedload(Expedicao.treinador),
        joinedload(Expedicao.local_destino),
        joinedload(Expedicao.local_origem),
        selectinload(Expedicao.itens).joinedload(ExpedicaoItem.item),
    )


def _com_relacoes(consulta: Select) -> Select:
    return _relacoes_base(consulta).options(
        # O relatorio (quando ja existe) precisa da linha do tempo inteira
        # numa unica consulta extra, nao uma por evento (plan.md: "cuidado
        # com N+1 ao montar o relatorio"). So carregada aqui: a ficha de UMA
        # expedicao e exatamente o lugar em que o professor quer a linha do
        # tempo inteira. `listar` (abaixo) nao usa isto de proposito —
        # revisao da Fase 7, achado 1.
        selectinload(Expedicao.eventos),
    )


# Teto padrao e maximo de `GET /expeditions` (revisao da Fase 7, achado 1):
# o painel so pede as N expedicoes mais recentes do laboratorio, nunca uma
# pagina especifica de um historico que so cresce. `LIMITE_MAXIMO` existe
# para o mesmo motivo de `PAGE_MAXIMA` em `repositories/pokemon.py`: um
# cliente mal comportado nao deve poder pedir o historico inteiro de uma vez.
LIMITE_PADRAO = 20
LIMITE_MAXIMO = 100


def listar(
    sessao: Session, laboratorio_id: uuid.UUID, limite: int = LIMITE_PADRAO
) -> list[Expedicao]:
    """As `limite` expedicoes mais recentes do laboratorio.

    Sem filtro de status aqui: `AGUARDANDO_RELATORIO` e derivado, nao e um
    valor de coluna, entao filtrar por estado observado e trabalho de
    `services/expedicoes.py`, que ja tem o relogio em maos (plan.md). O corte
    por `limite` acontece ANTES desse filtro, na propria consulta: a listagem
    promete "as N mais recentes", nao "as N mais recentes depois de filtrar",
    e so a primeira leitura e barata — ler o historico inteiro para filtrar
    depois era exatamente o problema que o teto resolve.

    Sem `selectinload(Expedicao.eventos)` (achado 1): a listagem nunca monta
    `relatorio`, entao buscar a linha do tempo de cada expedicao aqui seria
    trabalho pago e nunca lido.
    """
    consulta = (
        _relacoes_base(select(Expedicao).where(Expedicao.laboratorio_id == laboratorio_id))
        .order_by(Expedicao.started_at.desc(), Expedicao.id)
        .limit(limite)
    )
    return list(sessao.scalars(consulta).unique())


def buscar_detalhe(
    sessao: Session, laboratorio_id: uuid.UUID, expedicao_id: uuid.UUID
) -> Expedicao | None:
    """Uma expedicao do laboratorio, com tudo que a ficha mostra.

    Escopado ao laboratorio na propria consulta: a expedicao de outro
    professor nunca chega a existir para quem pergunta (404, nunca 403).
    """
    consulta = _com_relacoes(
        select(Expedicao).where(
            Expedicao.laboratorio_id == laboratorio_id, Expedicao.id == expedicao_id
        )
    )
    return sessao.scalars(consulta).unique().one_or_none()


def travar_para_abortar(
    sessao: Session, laboratorio_id: uuid.UUID, expedicao_id: uuid.UUID
) -> Expedicao | None:
    """`SELECT ... FOR UPDATE` na expedicao, para checar e mudar o status sob lock.

    So a linha da expedicao, sem os relacionamentos: o aborto le `status` e
    `eta`, decide, e grava — a ficha completa para a resposta vem de uma
    segunda leitura, ja sem lock, depois do commit (mesmo padrao de
    `trainers_service.definir_time`).

    Sem `populate_existing` (auditoria da revisao da Fase 7): nenhum `Expedicao`
    e lido antes deste lock na mesma transacao — `abortar()` nao chama
    `buscar_detalhe` primeiro — entao esta e sempre a primeira vez que a linha
    entra no identity map da sessao. Nao ha valor antigo para preservar por
    engano.
    """
    return sessao.scalar(
        select(Expedicao)
        .where(Expedicao.laboratorio_id == laboratorio_id, Expedicao.id == expedicao_id)
        .with_for_update()
    )


def criar(
    sessao: Session,
    *,
    laboratorio_id: uuid.UUID,
    despacho: DespachoCalculado,
    especies_vistas_no_envio: Sequence[int],
) -> Expedicao:
    """Grava a expedicao e a carga que `calcular_despacho` ja aprovou.

    Sem commit aqui: quem abre e fecha a transacao e `services/expedicoes.py`,
    depois de debitar o estoque com o mesmo lock — a escrita da expedicao e
    o debito tem que entrar juntos ou nenhum dos dois entra.

    `especies_vistas_no_envio` e o retrato da Pokedex do laboratorio NO
    INSTANTE DO DESPACHO (achado 3 da revisao da Fase 7): e com ele, nunca com
    uma leitura da Pokedex no `claim`, que a resolucao decide quais encontros
    sao `DESCOBERTA` — assim o relatorio continua sendo, ao pe da letra,
    funcao so da semente e do estado gravado no envio (invariante 19).
    """
    expedicao = Expedicao(
        laboratorio_id=laboratorio_id,
        treinador_id=despacho.treinador_id,
        local_destino_id=despacho.destino_id,
        local_origem_id=despacho.origem_id,
        status="EM_CURSO",
        seed=despacho.seed,
        started_at=despacho.started_at,
        eta=despacho.eta,
        duracao_minutos=despacho.duracao_minutos,
        dificuldade_calculada=despacho.dificuldade,
        poder_time_calculado=despacho.poder_time,
        especies_vistas_no_envio=sorted(especies_vistas_no_envio),
    )
    sessao.add(expedicao)
    sessao.flush()  # garante expedicao.id antes de gravar a carga

    for item in despacho.carga:
        sessao.add(
            ExpedicaoItem(
                expedicao_id=expedicao.id,
                item_id=item.item_id,
                quantidade_levada=item.quantidade,
                quantidade_consumida=0,
            )
        )
    return expedicao


# --- Resolucao (spec 007) ----------------------------------------------------


def travar_para_resolver(
    sessao: Session, laboratorio_id: uuid.UUID, expedicao_id: uuid.UUID
) -> Expedicao | None:
    """`SELECT ... FOR UPDATE` so na linha da expedicao (Artigo VII, ADR-006).

    Sem nenhum `joinedload`/`selectinload` aqui: o Postgres recusa `FOR
    UPDATE` sobre um LEFT OUTER JOIN, e e exatamente o que `joinedload` usa
    por padrao. As relacoes que o claim precisa — treinador com o time e a
    especie de cada membro, locais, carga — vem de consultas proprias depois
    que o lock desta linha ja foi obtido, mesmo padrao de
    `treinadores_repo.travar_treinador_com_time`.

    Sem `populate_existing`, mesmo motivo de `travar_para_abortar`: `claim()`
    nunca le esta expedicao por outro caminho antes de travar — e a primeira
    linha da funcao — entao nao ha objeto preexistente no identity map para
    o `SELECT ... FOR UPDATE` deixar de atualizar.
    """
    return sessao.scalar(
        select(Expedicao)
        .where(Expedicao.laboratorio_id == laboratorio_id, Expedicao.id == expedicao_id)
        .with_for_update()
    )


def gravar_eventos(
    sessao: Session, expedicao_id: uuid.UUID, eventos: Sequence[EventoDeCampo]
) -> None:
    """Grava a linha do tempo inteira, uma linha de `ExpedicaoEvento` por evento."""
    for evento in eventos:
        sessao.add(
            ExpedicaoEvento(
                expedicao_id=expedicao_id,
                ordem=evento.ordem,
                tipo=evento.tipo.value,
                texto=evento.texto,
                payload=evento.payload,
                ocorrido_em_minuto=evento.ocorrido_em_minuto,
            )
        )


def atualizar_consumo_itens(
    sessao: Session, expedicao_id: uuid.UUID, consumidos: Sequence[ItemDoRelatorio]
) -> None:
    """Debita da CARGA da expedicao, nunca do estoque do laboratorio (regra 17).

    `quantidade_consumida` e gravado direto com o total do relatorio, nao
    incrementado: esta e a primeira e unica vez que a expedicao resolve
    (Artigo VII), entao nao ha consumo anterior para somar.
    """
    for item in consumidos:
        sessao.execute(
            update(ExpedicaoItem)
            .where(
                ExpedicaoItem.expedicao_id == expedicao_id,
                ExpedicaoItem.item_id == item.item_id,
            )
            .values(quantidade_consumida=item.quantidade)
        )


def marcar_resolvida(
    expedicao: Expedicao, *, status: str, resolvida_em: datetime, resumo: dict
) -> None:
    """Grava o resultado final: status, instante da resolucao e o resumo do relatorio."""
    expedicao.status = status
    expedicao.resolvida_em = resolvida_em
    expedicao.relatorio_resumo = resumo
