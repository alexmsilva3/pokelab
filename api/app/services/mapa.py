"""Caso de uso do mapa de Kanto (spec 005).

So leitura: monta o grafo e o conjunto de visitados a partir do banco, chama
`app.game.mapa.visao_do_mapa` **uma vez** por requisicao e traduz o resultado
para o schema de saida. Nenhuma regra de alcance, de rota ou de duracao mora
aqui — isso e `game/mapa.py`, e duplica-la neste arquivo e o erro que o
Artigo I existe para evitar.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.erros import LocalNaoEncontrado, RecursoNaoEncontrado
from app.game.mapa import (
    GrafoDeLocais,
    LocalDesconhecido,
    LocalNoGrafo,
    LocalNoMapa,
    montar_grafo,
    visao_do_mapa,
)
from app.models import Local
from app.repositories import mapa as mapa_repo
from app.repositories import treinadores as treinadores_repo
from app.schemas.mapa import EspecieAvistadaLer, LocalDetalhadoLer, LocalNoMapaLer, MapaLer


def _montar_grafo(locais: list[Local]) -> GrafoDeLocais:
    """Traduz os `Local` do ORM para o `LocalNoGrafo` que o dominio entende.

    Nenhum `Local` do SQLAlchemy atravessa a fronteira de `game/` (Artigo I):
    so os quatro campos de que o grafo precisa.
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


def _linha_do_mapa(linha: LocalNoMapa, locais_por_id: dict[str, Local]) -> LocalNoMapaLer:
    """Junta o que o dominio calculou com o que o seed descreve sobre o local.

    `origem_nome` e `proximo_passo_nome` vem do mesmo dicionario que ja foi
    lido para montar o grafo — nenhuma consulta nova por nome.
    """
    local = locais_por_id[linha.id]
    origem = locais_por_id.get(linha.origem_id) if linha.origem_id else None
    proximo_passo = locais_por_id.get(linha.proximo_passo_id) if linha.proximo_passo_id else None
    return LocalNoMapaLer(
        id=local.id,
        nome=local.nome,
        tipo=local.tipo,
        nivel_dificuldade=local.nivel_dificuldade,
        nivel_selvagem_min=local.nivel_selvagem_min,
        nivel_selvagem_max=local.nivel_selvagem_max,
        estado=linha.estado.value,
        origem_id=linha.origem_id,
        origem_nome=origem.nome if origem else None,
        duracao_estimada_minutos=linha.duracao_estimada_minutos,
        proximo_passo_id=linha.proximo_passo_id,
        proximo_passo_nome=proximo_passo.nome if proximo_passo else None,
    )


def obter_mapa(sessao: Session, laboratorio_id: uuid.UUID) -> MapaLer:
    """Os dez locais do laboratorio, cada um com seu estado (regra 1).

    Duas consultas alimentam a resposta inteira — `listar_locais` e
    `listar_visitados` — e uma unica chamada a `visao_do_mapa` resolve as
    rotas de todos os dez de uma vez (plan.md: "dez locais, mas duas
    consultas, nao onze").

    Sem `treinador_id` aqui: a lista mostra a duracao **base**, sem o desconto
    de nivel de ninguem em particular — essa pergunta e a de `GET /map/{id}`.
    """
    locais = mapa_repo.listar_locais(sessao)
    locais_por_id = {local.id: local for local in locais}
    visitados = mapa_repo.listar_visitados(sessao, laboratorio_id)

    grafo = _montar_grafo(locais)
    escala = get_settings().expedition_time_scale
    linhas = visao_do_mapa(grafo, visitados, escala=escala)

    items = [_linha_do_mapa(linha, locais_por_id) for linha in linhas]
    return MapaLer(
        items=items,
        visitados=sum(1 for item in items if item.estado == "VISITADO"),
        total=len(items),
    )


def obter_local(
    sessao: Session,
    laboratorio_id: uuid.UUID,
    local_id: str,
    treinador_id: uuid.UUID | None,
) -> LocalDetalhadoLer:
    """O detalhe de um local: o mesmo do mapa, mais fauna ja avistada.

    `treinador_id` e opcional (plan.md): sem ele a duracao e a base, igual a
    de `GET /map`; com ele, e a duracao que **aquele** treinador teria, com o
    desconto do nivel dele — a pergunta real do professor ao escolher quem
    despachar. Um `treinador_id` de outro laboratorio nunca existe para quem
    pergunta (404, nunca 403), igual a qualquer outro recurso da API.
    """
    locais = mapa_repo.listar_locais(sessao)
    locais_por_id = {local.id: local for local in locais}
    grafo = _montar_grafo(locais)

    try:
        grafo.local(local_id)
    except LocalDesconhecido as erro:
        raise LocalNaoEncontrado(erro) from erro

    nivel_treinador = None
    if treinador_id is not None:
        treinador = treinadores_repo.buscar_por_id(sessao, laboratorio_id, treinador_id)
        if treinador is None:
            raise RecursoNaoEncontrado()
        nivel_treinador = treinador.nivel

    visitados = mapa_repo.listar_visitados(sessao, laboratorio_id)
    escala = get_settings().expedition_time_scale
    linhas_por_id = {
        linha.id: linha
        for linha in visao_do_mapa(grafo, visitados, nivel_treinador=nivel_treinador, escala=escala)
    }
    linha = _linha_do_mapa(linhas_por_id[local_id], locais_por_id)

    avistamentos = mapa_repo.listar_avistamentos(sessao, laboratorio_id, local_id)
    local = locais_por_id[local_id]

    return LocalDetalhadoLer(
        **linha.model_dump(),
        encontros_base=local.encontros_base,
        especies_avistadas=[
            EspecieAvistadaLer(
                especie_id=avistamento.especie.id,
                nome=avistamento.especie.nome,
                sprite=avistamento.especie.sprite_frente,
                vezes_visto=avistamento.vezes_visto,
                primeiro_visto_em=avistamento.primeiro_visto_em,
            )
            for avistamento in avistamentos
        ],
    )
