"""Caso de uso do viveiro (spec 008): `GET /ranch`.

So leitura, no mesmo espirito de `services/mapa.py`: busca o que o banco tem,
chama `app.game.viveiro` para o retrato de ocupacao e transbordo, e traduz
para o schema de saida. Nenhuma regra de capacidade mora aqui — a unica guarda
de despacho do viveiro vive no servico de despacho de expedicao (tarefa 15),
nao nesta leitura.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.game.viveiro import estado_do_viveiro
from app.repositories import pokemon as pokemon_repo
from app.schemas.pokemon import PokemonResumo
from app.schemas.viveiro import EstadoDoViveiroLer
from app.services import relogio


def obter(sessao: Session, laboratorio_id: uuid.UUID) -> EstadoDoViveiroLer:
    """Quem esta no viveiro agora, mais capacidade e transbordo (criterios 1 e 2).

    Todo item desta lista tem `treinador_id` nulo (e e por isso que o
    repositorio ja filtra assim): nenhum deles pode estar `EM_EXPEDICAO`, e a
    recuperacao passiva sempre corre para quem esta aqui (invariante 18) — sem
    o desvio que `services.pokemon._hp_observado` faz para quem esta em campo.
    """
    agora = datetime.now(UTC)
    escala = get_settings().expedition_time_scale

    pokemon = pokemon_repo.listar_viveiro(sessao, laboratorio_id)
    ocupacao_atual = len(pokemon)
    estado = estado_do_viveiro(ocupacao_atual)

    items = [
        PokemonResumo.de_modelo(
            item,
            hp_atual_pct=relogio.hp_observado(
                item.hp_atual_pct, item.hp_atualizado_em, agora=agora, escala=escala
            ),
        )
        for item in pokemon
    ]

    return EstadoDoViveiroLer(
        capacidade=estado.capacidade,
        ocupacao=estado.ocupacao,
        transbordado=estado.transbordado,
        lugares_faltando=estado.lugares_faltando,
        items=items,
    )
