"""Acesso as tabelas `entregas` e `entrega_requisitos` (spec 008, SDD 4.9).

`GET /deliveries` precisa dos requisitos, do local de destino e do treinador
(quando ha um) numa unica leitura, mesmo cuidado com N+1 de
`repositories/expedicoes.py`: `joinedload` para os dois escalares,
`selectinload` para os requisitos (uma consulta por tabela, nao uma por
entrega).

A escrita de cada fase do ciclo de vida de uma entrega mora aqui:
`criar_pedidos` (geracao), `travar_para_aceitar`/`marcar_aceita` (aceite,
tarefa 13), `travar_para_resolver`/`marcar_concluida` (conclusao, tarefa 14,
ADR-006) e `marcar_descartadas` (regeracao da lista cheia, tarefa 12).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.game.delivery import PedidoDeEntrega, StatusEntrega
from app.models import Entrega, EntregaRequisito


def _com_relacoes(consulta: Select) -> Select:
    return consulta.options(
        joinedload(Entrega.local_destino),
        joinedload(Entrega.treinador),
        selectinload(Entrega.requisitos).joinedload(EntregaRequisito.especie),
    )


# Teto padrao e maximo de `listar` (revisao da Fase 8, achado "listagem sem
# teto" — mesmo defeito que a Fase 7 teve em `repositories/expedicoes.py`,
# corrigido la do mesmo jeito): cada descarte deixa pedidos `DESCARTADA`
# permanentes, cada expiracao natural deixa um `DISPONIVEL` zumbi que nunca
# mais muda de status (invariante 17 — expiracao nunca e gravada), e cada
# conclusao deixa mais um `CONCLUIDA`. Sem teto, `GET /deliveries` cresce pra
# sempre. `LIMITE_PADRAO` e generoso o bastante para nunca cortar um pedido
# `DISPONIVEL` ainda valido: um pedido so continua `DISPONIVEL` observado
# enquanto `expira_em > agora`, e isso significa que ele foi `gerada_em`
# dentro da janela de validade — ou seja, e sempre um dos mais RECENTES, e
# `ORDER BY gerada_em DESC` o traz para dentro do teto de qualquer jeito.
LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200


def listar(
    sessao: Session, laboratorio_id: uuid.UUID, limite: int = LIMITE_PADRAO
) -> list[Entrega]:
    """As `limite` entregas mais recentes do laboratorio (mais recente primeiro).

    Sem filtro de status aqui: `EXPIRADA` e derivada, nunca gravada
    (criterio 19), entao filtrar por estado observado e trabalho do servico,
    que tem o relogio em maos (Artigo I). O corte por `limite` acontece ANTES
    desse filtro, na propria consulta — ver o comentario de `LIMITE_PADRAO`
    sobre por que isso nunca esconde um pedido `DISPONIVEL` ainda valido.
    """
    consulta = (
        _com_relacoes(select(Entrega).where(Entrega.laboratorio_id == laboratorio_id))
        .order_by(Entrega.gerada_em.desc(), Entrega.id.desc())
        .limit(limite)
    )
    return list(sessao.scalars(consulta).unique())


def buscar_detalhe(
    sessao: Session, laboratorio_id: uuid.UUID, entrega_id: uuid.UUID
) -> Entrega | None:
    """Uma entrega do laboratorio, com tudo que a ficha mostra.

    Escopado ao laboratorio na propria consulta: a entrega de outro professor
    nunca chega a existir para quem pergunta (404, nunca 403, criterio 32).
    """
    consulta = _com_relacoes(
        select(Entrega).where(Entrega.laboratorio_id == laboratorio_id, Entrega.id == entrega_id)
    )
    return sessao.scalars(consulta).unique().one_or_none()


def criar_pedidos(
    sessao: Session,
    *,
    laboratorio_id: uuid.UUID,
    pedidos: Sequence[PedidoDeEntrega],
    gerada_em: datetime,
    expira_em: datetime,
) -> list[Entrega]:
    """Grava os pedidos que `game.delivery.gerar_pedidos` ja sorteou.

    Sem commit aqui: quem abre e fecha a transacao e `services/entregas.py`.
    `status` nasce `DISPONIVEL` e as colunas do aceite (treinador, prazo da
    missao, recompensa) nascem nulas — elas so existem a partir do aceite
    (tarefa 13).
    """
    entregas: list[Entrega] = []
    for pedido in pedidos:
        entrega = Entrega(
            laboratorio_id=laboratorio_id,
            titulo=pedido.titulo,
            local_destino_id=pedido.local_destino_id,
            status=StatusEntrega.DISPONIVEL.value,
            gerada_em=gerada_em,
            expira_em=expira_em,
        )
        sessao.add(entrega)
        sessao.flush()  # garante entrega.id antes dos requisitos
        for requisito in pedido.requisitos:
            sessao.add(
                EntregaRequisito(
                    entrega_id=entrega.id,
                    especie_id=requisito.especie_id,
                    quantidade=requisito.quantidade,
                )
            )
        entregas.append(entrega)
    return entregas


# --- Aceite (tarefa 13, criterios 20 e 23 a 26) ------------------------------


def travar_para_aceitar(
    sessao: Session, laboratorio_id: uuid.UUID, entrega_id: uuid.UUID
) -> Entrega | None:
    """`SELECT ... FOR UPDATE` so na linha da entrega (Artigo VII).

    Sem `joinedload`/`selectinload`: o Postgres recusa `FOR UPDATE` sobre um
    LEFT OUTER JOIN (mesmo motivo de `expedicoes_repo.travar_para_resolver`).
    Os requisitos vem de `buscar_requisitos`, numa consulta separada e sem
    lock — eles nunca mudam depois de criados (nenhuma rota os atualiza),
    entao uma leitura sem trava e segura mesmo sob concorrencia.
    """
    return sessao.scalar(
        select(Entrega)
        .where(Entrega.laboratorio_id == laboratorio_id, Entrega.id == entrega_id)
        .with_for_update()
    )


def travar_varias(
    sessao: Session, laboratorio_id: uuid.UUID, entrega_ids: Sequence[uuid.UUID]
) -> list[Entrega]:
    """`SELECT ... FOR UPDATE` em varias entregas, ordenadas por id (Artigo VII).

    Usada pelo descarte da lista cheia em `services/entregas.py::refresh`:
    as entregas que vao virar `DESCARTADA` precisam estar travadas ANTES do
    laboratorio (ordem canonica — ver `pokemon_service.soltar`), senao um
    `refresh` descartando e um `aceitar` concorrente sobre o MESMO pedido
    travariam laboratorio-depois-entrega de um lado e entrega-depois-
    laboratorio do outro: deadlock classico. Ordenado por `id`, mesmo
    raciocinio de `pokemon_repo.travar_varios`: duas chamadas que travassem o
    mesmo conjunto em ordens diferentes entre si tambem deadlockariam.
    """
    if not entrega_ids:
        return []
    consulta = (
        select(Entrega)
        .where(Entrega.laboratorio_id == laboratorio_id, Entrega.id.in_(entrega_ids))
        .order_by(Entrega.id)
        .with_for_update()
    )
    return list(sessao.scalars(consulta))


def buscar_requisitos(sessao: Session, entrega_id: uuid.UUID) -> list[EntregaRequisito]:
    """Os requisitos de uma entrega, em ordem canonica de `especie_id`, com o
    nome da especie ja junto (o aceite precisa dele para a mensagem de recusa)."""
    return list(
        sessao.scalars(
            select(EntregaRequisito)
            .where(EntregaRequisito.entrega_id == entrega_id)
            .options(joinedload(EntregaRequisito.especie))
            .order_by(EntregaRequisito.especie_id)
        )
    )


def marcar_aceita(
    entrega: Entrega,
    *,
    treinador_id: uuid.UUID,
    started_at: datetime,
    eta: datetime,
    duracao_minutos: int,
    recompensa_moedas: int,
    recompensa_exp_laboratorio: int,
    recompensa_exp_treinador: int,
) -> None:
    """Grava o aceite: a entrega vira viagem com `eta` proprio (SDD 4.9).

    `expira_em` **nao** e limpo aqui de proposito: a coluna continua com o
    prazo antigo da oferta, mas deixa de significar qualquer coisa a partir
    daqui, porque `StatusEntrega.aceita_prazo_da_oferta` so e verdadeiro em
    `DISPONIVEL` — apagar o valor so destruiria historico sem necessidade.
    A recompensa e gravada AGORA, com o nivel real de cada Pokemon escolhido:
    a conclusao (`claim`) so le estas colunas, nunca recalcula.
    """
    entrega.status = StatusEntrega.EM_CURSO.value
    entrega.treinador_id = treinador_id
    entrega.started_at = started_at
    entrega.eta = eta
    entrega.duracao_minutos = duracao_minutos
    entrega.recompensa_moedas = recompensa_moedas
    entrega.recompensa_exp_laboratorio = recompensa_exp_laboratorio
    entrega.recompensa_exp_treinador = recompensa_exp_treinador


# --- Conclusao (tarefa 14, ADR-006, criterios 27 a 30) -----------------------


def travar_para_resolver(
    sessao: Session, laboratorio_id: uuid.UUID, entrega_id: uuid.UUID
) -> Entrega | None:
    """`SELECT ... FOR UPDATE` so na linha da entrega (Artigo VII, ADR-006).

    Mesmo padrao de `expedicoes_repo.travar_para_resolver`: a PRIMEIRA
    operacao destrutiva do jogo (plan.md) merece o mesmo cuidado que a
    resolucao de expedicao, e o lock aqui e o que torna a segunda chamada
    concorrente uma releitura, nunca uma segunda escrita.
    """
    return sessao.scalar(
        select(Entrega)
        .where(Entrega.laboratorio_id == laboratorio_id, Entrega.id == entrega_id)
        .with_for_update()
    )


def marcar_concluida(entrega: Entrega, *, resolvida_em: datetime, resultado_resumo: dict) -> None:
    """Grava o fim do ciclo (criterios 27, 29 e 30 da spec 008).

    A recompensa ja estava gravada desde o aceite (regra 24); `resultado_resumo`
    e o que falta — os Pokemon entregues (que deixam de existir) e o
    antes-e-depois de nivel que uma segunda leitura nao pode recalcular
    (mesmo motivo de `expedicoes_repo.marcar_resolvida`).
    """
    entrega.status = StatusEntrega.CONCLUIDA.value
    entrega.resolvida_em = resolvida_em
    entrega.resultado_resumo = resultado_resumo


# --- Regeracao da lista (tarefa 12, invariantes 15, 18 e 23) ----------------


def marcar_descartadas(sessao: Session, entregas: Sequence[Entrega]) -> None:
    """Marca como `DESCARTADA` os pedidos ainda validos, para a lista regerar.

    So chamada quando `vagas_para_repor == 0` (nenhuma vaga aberta por
    expiracao ou aceite): descartar a lista inteira por nao gostar dela e o
    gesto que consome `INTERVALO_REGERAR_ENTREGAS` (invariante 19/regra 19).
    """
    for entrega in entregas:
        entrega.status = StatusEntrega.DESCARTADA.value
