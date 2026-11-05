"""Persistencia da descricao que `app.game.kit_inicial` devolve.

O dominio so descreve; este modulo e quem materializa a descricao nas tabelas
de estado, dentro da transacao que o servico de registro controla.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.game.kit_inicial import KitInicial
from app.models import ItemEstoque, LocalDesbloqueado, PokedexEntrada, PokemonInstancia, Treinador

HP_INICIAL_PCT = 100
ORIGEM_INICIAL = "INICIAL"
STATUS_DISPONIVEL = "DISPONIVEL"


def persistir(
    sessao: Session, laboratorio_id: uuid.UUID, kit: KitInicial, *, agora: datetime
) -> list[Treinador]:
    """Grava os starters, o treinador, o estoque, o local e a Pokedex do kit.

    Devolve os `Treinador` criados, na mesma ordem de `kit.treinadores`.
    """
    for pokemon in kit.pokemon:
        sessao.add(
            PokemonInstancia(
                laboratorio_id=laboratorio_id,
                especie_id=pokemon.especie_id,
                nivel=pokemon.nivel,
                experiencia=pokemon.experiencia,
                hp_atual_pct=HP_INICIAL_PCT,
                treinador_id=None,
                origem=ORIGEM_INICIAL,
                local_captura_id=None,
                capturado_em=agora,
            )
        )

    treinadores = [
        Treinador(
            laboratorio_id=laboratorio_id,
            nome=treinador.nome,
            avatar=treinador.avatar.para_dicionario(),
            nivel=1,
            experiencia=0,
            status=STATUS_DISPONIVEL,
        )
        for treinador in kit.treinadores
    ]
    sessao.add_all(treinadores)

    for item in kit.itens:
        sessao.add(
            ItemEstoque(
                laboratorio_id=laboratorio_id, item_id=item.item_id, quantidade=item.quantidade
            )
        )

    for local_id in kit.locais_desbloqueados:
        sessao.add(
            LocalDesbloqueado(
                laboratorio_id=laboratorio_id, local_id=local_id, desbloqueado_em=agora
            )
        )

    for entrada in kit.pokedex:
        sessao.add(
            PokedexEntrada(
                laboratorio_id=laboratorio_id,
                especie_id=entrada.especie_id,
                visto=entrada.visto,
                capturado=entrada.capturado,
                primeiro_visto_em=agora,
            )
        )

    sessao.flush()
    return treinadores
