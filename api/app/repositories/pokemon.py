"""Acesso a tabela `pokemon_instancias` (spec 003).

A listagem precisa do nome, dos tipos e do sprite, que moram em
`pokemon_especies`. O risco e N+1: uma consulta por pagina viraria uma
consulta por Pokemon se a especie fosse buscada lazy, uma por item. O `join`
mais `contains_eager` abaixo resolve os dois problemas com a MESMA consulta —
filtrar por tipo e preencher `PokemonInstancia.especie` sem round-trip extra.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session, contains_eager, joinedload

from app.models import PokemonEspecie, PokemonInstancia

ORIGEM_CAPTURADO = "CAPTURADO"

PAGE_SIZE_PADRAO = 20
# Teto de protecao, nao regra de negocio: pedido acima disso e cortado em
# silencio (plan.md), nunca recusado.
# Teto de pagina. O router ja recusa acima disto com 422; aqui e a segunda
# linha de defesa, para que nenhum outro chamador estoure o OFFSET do Postgres.
PAGE_MAXIMA = 1_000_000
PAGE_SIZE_MAXIMO = 100


@dataclass(frozen=True, slots=True)
class FiltrosPokemon:
    """Os filtros combinaveis de `GET /pokemon`.

    `atribuido` e booleano de tres estados: `None` nao filtra, `True` traz so
    quem tem treinador, `False` so quem esta livre no laboratorio.

    `livre` e um conceito mais largo que `atribuido=False` (spec 004, secao 7
    do plano): hoje "livre" significa so "sem treinador", porque a Fase 8 ainda
    nao existe, mas o nome ja e o definitivo — "sem treinador E sem entrega".
    Quando `comprometido_entrega_id` for criado, a condicao de `livre` ganha
    mais uma clausula aqui, e `atribuido` continua como esta: os dois filtros
    respondem perguntas diferentes e nao devem ser fundidos num so.
    """

    tipo: str | None = None
    nivel_min: int | None = None
    nivel_max: int | None = None
    atribuido: bool | None = None
    livre: bool | None = None


def _condicoes(laboratorio_id: uuid.UUID, filtros: FiltrosPokemon) -> list:
    condicoes: list = [PokemonInstancia.laboratorio_id == laboratorio_id]

    if filtros.tipo is not None:
        # "casa com primario OU secundario" (plan.md) — um dos dois basta.
        condicoes.append(
            (PokemonEspecie.tipo_primario == filtros.tipo)
            | (PokemonEspecie.tipo_secundario == filtros.tipo)
        )
    if filtros.nivel_min is not None:
        condicoes.append(PokemonInstancia.nivel >= filtros.nivel_min)
    if filtros.nivel_max is not None:
        condicoes.append(PokemonInstancia.nivel <= filtros.nivel_max)
    if filtros.atribuido is True:
        condicoes.append(PokemonInstancia.treinador_id.is_not(None))
    elif filtros.atribuido is False:
        condicoes.append(PokemonInstancia.treinador_id.is_(None))

    if filtros.livre is True:
        # Fase 8 (spec 008, invariante 14): "livre" agora e "sem treinador E
        # sem entrega". Um Pokemon comprometido nao tem treinador_id (ele
        # continua no viveiro ate a conclusao), entao sem esta segunda
        # clausula ele aparecia como livre para `PUT /trainers/{id}/team` —
        # exatamente o que o invariante 14 proibe.
        condicoes.append(
            PokemonInstancia.treinador_id.is_(None),
        )
        condicoes.append(PokemonInstancia.comprometido_entrega_id.is_(None))
    elif filtros.livre is False:
        condicoes.append(
            PokemonInstancia.treinador_id.is_not(None)
            | PokemonInstancia.comprometido_entrega_id.is_not(None)
        )

    return condicoes


def _query_juntada(laboratorio_id: uuid.UUID, filtros: FiltrosPokemon) -> Select:
    """Um unico join com a especie, usado tanto para filtrar quanto para contar."""
    return (
        select(PokemonInstancia)
        .join(PokemonInstancia.especie)
        .where(*_condicoes(laboratorio_id, filtros))
    )


def listar(
    sessao: Session,
    laboratorio_id: uuid.UUID,
    filtros: FiltrosPokemon,
    *,
    page: int,
    page_size: int,
) -> tuple[list[PokemonInstancia], int, int, int]:
    """Devolve a pagina, o total, e `page`/`page_size` ja normalizados.

    Ordenacao deterministica com desempate por `id`: sem isso o Postgres pode
    devolver a mesma linha em duas paginas diferentes, ou pular uma, quando
    duas linhas empatam no criterio principal.

    Devolve exatamente DUAS consultas, qualquer que seja o tamanho da pagina:
    uma de contagem, uma de dados com a especie ja junta via `contains_eager`.
    """
    page = min(max(page, 1), PAGE_MAXIMA)
    page_size = min(max(page_size, 1), PAGE_SIZE_MAXIMO)

    total = (
        sessao.scalar(
            select(func.count()).select_from(_query_juntada(laboratorio_id, filtros).subquery())
        )
        or 0
    )

    itens = list(
        sessao.scalars(
            _query_juntada(laboratorio_id, filtros)
            .options(
                contains_eager(PokemonInstancia.especie),
                # O servico precisa do STATUS do treinador para derivar o HP
                # (invariante 18: em campo a enfermaria nao conta) sem uma
                # consulta por linha — ver `services.pokemon._hp_observado`.
                joinedload(PokemonInstancia.treinador),
            )
            .order_by(PokemonInstancia.nivel.desc(), PokemonInstancia.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )

    return itens, total, page, page_size


def buscar_detalhe(
    sessao: Session, laboratorio_id: uuid.UUID, pokemon_id: uuid.UUID
) -> PokemonInstancia | None:
    """Um Pokemon do laboratorio, com especie, treinador e local de captura.

    Filtra por `laboratorio_id` na propria consulta: um id de outro
    laboratorio nunca chega a existir para quem pergunta (404, nunca 403).
    """
    return sessao.scalar(
        select(PokemonInstancia)
        .where(
            PokemonInstancia.laboratorio_id == laboratorio_id,
            PokemonInstancia.id == pokemon_id,
        )
        .options(
            joinedload(PokemonInstancia.especie),
            joinedload(PokemonInstancia.treinador),
            joinedload(PokemonInstancia.local_captura),
        )
    )


def atualizar_apelido(pokemon: PokemonInstancia, apelido: str | None) -> None:
    pokemon.apelido = apelido


def atualizar_apos_expedicao(
    pokemon: PokemonInstancia,
    *,
    nivel: int,
    experiencia: int,
    especie_id: int,
    hp_atual_pct: int,
    hp_atualizado_em: datetime,
) -> None:
    """Grava o antes-e-depois que `game.expedition.resolver` ja decidiu (spec 007).

    `especie_id` muda quando o Pokemon evoluiu (`PokemonAposExpedicao.especie_final_id`
    ja resolve os dois casos); `hp_atualizado_em` recebe `resolvida_em`, que e
    quando a enfermaria volta a contar para este Pokemon (invariante 18).
    """
    pokemon.nivel = nivel
    pokemon.experiencia = experiencia
    pokemon.especie_id = especie_id
    pokemon.hp_atual_pct = hp_atual_pct
    pokemon.hp_atualizado_em = hp_atualizado_em


def criar_capturado(
    sessao: Session,
    *,
    id: uuid.UUID,
    laboratorio_id: uuid.UUID,
    especie_id: int,
    nivel: int,
    experiencia: int,
    hp_atual_pct: int,
    local_captura_id: str,
    capturado_em: datetime,
) -> PokemonInstancia:
    """Grava uma captura de campo: solta no laboratorio, nunca no time (regra 19).

    `id` chega pronto de quem chama, e nao e gerado aqui: o servico precisa do
    mesmo UUID tanto para a linha nova quanto para `relatorio_resumo.capturas`,
    gravado na mesma transacao — gerar em dois lugares produziria dois ids
    para o mesmo Pokemon.
    """
    pokemon = PokemonInstancia(
        id=id,
        laboratorio_id=laboratorio_id,
        especie_id=especie_id,
        nivel=nivel,
        experiencia=experiencia,
        hp_atual_pct=hp_atual_pct,
        hp_atualizado_em=capturado_em,
        treinador_id=None,
        origem=ORIGEM_CAPTURADO,
        local_captura_id=local_captura_id,
        capturado_em=capturado_em,
    )
    sessao.add(pokemon)
    return pokemon


# --- Viveiro e soltura (Fase 8, spec 008) ------------------------------------


def listar_viveiro(sessao: Session, laboratorio_id: uuid.UUID) -> list[PokemonInstancia]:
    """Os Pokemon do viveiro: `treinador_id` nulo (`game.viveiro.no_viveiro`).

    Inclui quem esta comprometido com uma entrega — ele ainda ocupa o lugar
    dele ate ela ser concluida (invariante 20) — e e exatamente por isso que o
    filtro e so sobre `treinador_id`, nao sobre `comprometido_entrega_id`.
    """
    consulta = (
        select(PokemonInstancia)
        .where(
            PokemonInstancia.laboratorio_id == laboratorio_id,
            PokemonInstancia.treinador_id.is_(None),
        )
        .options(joinedload(PokemonInstancia.especie))
        .order_by(PokemonInstancia.nivel.desc(), PokemonInstancia.id)
    )
    return list(sessao.scalars(consulta))


def contar_viveiro(sessao: Session, laboratorio_id: uuid.UUID) -> int:
    """A ocupacao do viveiro (invariante 20): `treinador_id` nulo, contagem pura.

    Usada pela guarda de despacho de `game.viveiro` (tarefa 15 da spec 008),
    que so precisa do NUMERO — `listar_viveiro` serve ao `GET /ranch`, que
    tambem precisa dos itens, e seria uma consulta mais cara para quem so
    quer o total.
    """
    return (
        sessao.scalar(
            select(func.count())
            .select_from(PokemonInstancia)
            .where(
                PokemonInstancia.laboratorio_id == laboratorio_id,
                PokemonInstancia.treinador_id.is_(None),
            )
        )
        or 0
    )


def contar(sessao: Session, laboratorio_id: uuid.UUID) -> int:
    """O total de Pokemon que CONTINUAM no laboratorio, dentro ou fora do viveiro.

    E o numero que `game.soltar.exigir_que_sobre_pokemon` compara com
    `POKEMON_MINIMOS_NO_LABORATORIO` (invariante 25): time e viveiro contam
    igual, porque os dois ainda pertencem ao laboratorio — mas um Pokemon JA
    `comprometido_entrega_id` NAO conta (achado critico da revisao da Fase
    8). Ele ainda existe fisicamente na tabela ate o `claim` da entrega dele
    apagar a linha, mas esse apagamento ja foi aprovado no aceite: contar
    esse Pokemon aqui como "fica" e o motivo do beco sem saida que a revisao
    reproduziu duas vezes contra o compose — a soltura E o aceite, cada um
    enxergando so a propria saida e tratando a saida JA AGENDADA do outro
    como acervo que fica, zeram o laboratorio juntos.

    As DUAS unicas chamadoras (`pokemon_service.soltar` e
    `entregas_service.aceitar`) chamam esta funcao ANTES de prometer o(s)
    Pokemon da PROPRIA operacao a uma entrega — o aceite roda isto antes de
    `pokemon_repo.comprometer`, entao os Pokemon que ELE esta prestes a
    comprometer ainda tem `comprometido_entrega_id` nulo aqui e SAO contados
    normalmente; so os comprometidos a OUTRAS entregas, de aceites
    anteriores, ficam de fora. `exigir_que_sobre_pokemon(total, saindo=N)`
    continua recebendo quantos ESTA operacao esta tirando.
    """
    return (
        sessao.scalar(
            select(func.count())
            .select_from(PokemonInstancia)
            .where(
                PokemonInstancia.laboratorio_id == laboratorio_id,
                PokemonInstancia.comprometido_entrega_id.is_(None),
            )
        )
        or 0
    )


def travar_para_soltar(
    sessao: Session, laboratorio_id: uuid.UUID, pokemon_id: uuid.UUID
) -> PokemonInstancia | None:
    """`SELECT ... FOR UPDATE` so na linha do Pokemon (Artigo VII).

    Sem `joinedload` de proposito, mesmo motivo de `expedicoes_repo.
    travar_para_resolver`: o Postgres recusa `FOR UPDATE` sobre um LEFT OUTER
    JOIN. `especie_id`, `treinador_id` e `comprometido_entrega_id` sao
    colunas escalares da propria linha — chegam travados sem precisar de
    nenhuma relacao carregada. Quem precisa do `Treinador` por tras (para ler
    o status) trava-o a parte, com `treinadores_repo.travar_treinador`.
    """
    return sessao.scalar(
        select(PokemonInstancia)
        .where(
            PokemonInstancia.laboratorio_id == laboratorio_id,
            PokemonInstancia.id == pokemon_id,
        )
        .with_for_update()
    )


def travar_varios(
    sessao: Session, laboratorio_id: uuid.UUID, pokemon_ids: Sequence[uuid.UUID]
) -> list[PokemonInstancia]:
    """`SELECT ... FOR UPDATE` nos Pokemon escolhidos para um aceite de entrega.

    Ordenado por `id` (Artigo VII, plan.md da spec 008 secao 13): duas
    transacoes que travam o MESMO conjunto em ordens diferentes e a receita
    classica de deadlock, mesmo raciocinio de
    `treinadores_repo.travar_pokemon_envolvidos`. Sem `joinedload`, mesmo
    motivo de `travar_para_soltar`.
    """
    if not pokemon_ids:
        return []
    consulta = (
        select(PokemonInstancia)
        .where(
            PokemonInstancia.laboratorio_id == laboratorio_id,
            PokemonInstancia.id.in_(pokemon_ids),
        )
        .order_by(PokemonInstancia.id)
        .with_for_update()
    )
    return list(sessao.scalars(consulta))


def excluir(sessao: Session, pokemon: PokemonInstancia) -> None:
    """Remove a linha de verdade (regra do DELETE /pokemon/{id}): sem soft delete,
    porque nao ha para que voltar (plan.md da spec 008)."""
    sessao.delete(pokemon)


def comprometer(pokemon: PokemonInstancia, entrega_id: uuid.UUID) -> None:
    """Marca o Pokemon como reservado para esta entrega (aceite, regra 20)."""
    pokemon.comprometido_entrega_id = entrega_id


def listar_comprometidos(
    sessao: Session, laboratorio_id: uuid.UUID, entrega_id: uuid.UUID
) -> list[PokemonInstancia]:
    """Os Pokemon reservados para esta entrega, travados para a conclusao.

    `FOR UPDATE` porque a conclusao (`claim`) e a primeira operacao
    DESTRUTIVA do jogo (plan.md): apagar a linha errada e irreparavel, e o
    lock garante que nenhuma outra transacao mexe nestes Pokemon enquanto o
    `claim` decide.
    """
    consulta = (
        select(PokemonInstancia)
        .where(
            PokemonInstancia.laboratorio_id == laboratorio_id,
            PokemonInstancia.comprometido_entrega_id == entrega_id,
        )
        .order_by(PokemonInstancia.id)
        .with_for_update()
    )
    return list(sessao.scalars(consulta))
