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

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.game.expedition import DespachoCalculado
from app.models import Expedicao, ExpedicaoItem


def _com_relacoes(consulta: Select) -> Select:
    return consulta.options(
        joinedload(Expedicao.treinador),
        joinedload(Expedicao.local_destino),
        joinedload(Expedicao.local_origem),
        selectinload(Expedicao.itens).joinedload(ExpedicaoItem.item),
    )


def listar(sessao: Session, laboratorio_id: uuid.UUID) -> list[Expedicao]:
    """As expedicoes do laboratorio, mais recentes primeiro.

    Sem filtro de status aqui: `AGUARDANDO_RELATORIO` e derivado, nao e um
    valor de coluna, entao filtrar por estado observado e trabalho de
    `services/expedicoes.py`, que ja tem o relogio em maos (plan.md).
    """
    consulta = _com_relacoes(
        select(Expedicao).where(Expedicao.laboratorio_id == laboratorio_id)
    ).order_by(Expedicao.started_at.desc(), Expedicao.id)
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
    """
    return sessao.scalar(
        select(Expedicao)
        .where(Expedicao.laboratorio_id == laboratorio_id, Expedicao.id == expedicao_id)
        .with_for_update()
    )


def criar(sessao: Session, *, laboratorio_id: uuid.UUID, despacho: DespachoCalculado) -> Expedicao:
    """Grava a expedicao e a carga que `calcular_despacho` ja aprovou.

    Sem commit aqui: quem abre e fecha a transacao e `services/expedicoes.py`,
    depois de debitar o estoque com o mesmo lock — a escrita da expedicao e
    o debito tem que entrar juntos ou nenhum dos dois entra.
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
