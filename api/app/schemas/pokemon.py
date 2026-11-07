"""Contrato de `/pokemon` (spec 003, secao 5.3 do SDD).

Entrada e saida sao classes separadas (Artigo II). `ApelidoAtualizar` e o
unico schema de entrada desta rota: nivel, experiencia, stats e EXP para o
proximo nivel sao sempre derivados pelo servidor, nunca aceitos do cliente.

`de_modelo` recebe `object` em vez do tipo ORM, no mesmo padrao de
`LaboratorioLer` em `schemas/auth.py`: o contrato nao depende de
`app.models`, so do shape que `PokemonInstancia` (com `especie` carregada)
satisfaz.
"""

from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.game.stats import StatsEfetivos

TAMANHO_MAXIMO_APELIDO = 50

# --- Entrada -----------------------------------------------------------------


class ApelidoAtualizar(BaseModel):
    apelido: str | None

    @field_validator("apelido")
    @classmethod
    def _validar(cls, valor: str | None) -> str | None:
        """Apara espacos; nulo limpa o apelido, so-espaco e recusado.

        A Fase 2 ja levou este achado no campo usuario: `min_length` sobre a
        string crua deixa "   " passar e grava vazio depois do `strip`. Aqui a
        checagem inteira — minimo, maximo, e o caso so-espaco — acontece
        depois de aparar, nunca antes.
        """
        if valor is None:
            return None
        aparado = valor.strip()
        if not aparado:
            raise ValueError("apelido nao pode ser composto apenas por espacos")
        if len(aparado) > TAMANHO_MAXIMO_APELIDO:
            raise ValueError(f"apelido pode ter no maximo {TAMANHO_MAXIMO_APELIDO} caracteres")
        return aparado


# --- Saida ---------------------------------------------------------------


class StatsEfetivosLer(BaseModel):
    hp: int
    ataque: int
    defesa: int
    ataque_especial: int
    defesa_especial: int
    velocidade: int

    @classmethod
    def de_dominio(cls, stats: StatsEfetivos) -> StatsEfetivosLer:
        return cls(**dataclasses.asdict(stats))


class PokemonResumo(BaseModel):
    """O que a lista mostra: imagem, nome, tipo e nivel (criterio 1)."""

    id: uuid.UUID
    nome: str
    # O apelido cru vai junto do nome ja resolvido. Sem ele o cliente deduzia
    # "tem apelido?" comparando nome com especie_nome, o que erra justamente
    # quando alguem apelida um Pidgey de "Pidgey".
    apelido: str | None
    especie_id: int
    especie_nome: str
    tipo_primario: str
    tipo_secundario: str | None
    sprite: str
    nivel: int
    atribuido: bool
    treinador_id: uuid.UUID | None
    # Derivado pelo servico a cada leitura (spec 007, criterios 20 e 21): o
    # valor CRU do banco nunca atravessa a API. `hp_atualizado_em` acompanha
    # para a interface poder explicar a recuperacao ("desde quando").
    hp_atual_pct: int
    hp_atualizado_em: datetime

    @classmethod
    def de_modelo(cls, pokemon: object, *, hp_atual_pct: int) -> PokemonResumo:
        """`pokemon` precisa chegar com `especie` ja carregada (sem lazy load).

        `hp_atual_pct` chega PRONTO, ja derivado pelo servico com
        `services.relogio.hp_observado` (Artigo I: ler o relogio e a escala
        de tempo e trabalho do servico, nao deste schema).
        """
        especie = pokemon.especie
        return cls(
            id=pokemon.id,
            # Regra 4: sem apelido, o nome exibido e o da especie.
            nome=pokemon.apelido or especie.nome,
            apelido=pokemon.apelido,
            especie_id=especie.id,
            especie_nome=especie.nome,
            tipo_primario=especie.tipo_primario,
            tipo_secundario=especie.tipo_secundario,
            sprite=especie.sprite_frente,
            nivel=pokemon.nivel,
            atribuido=pokemon.treinador_id is not None,
            treinador_id=pokemon.treinador_id,
            hp_atual_pct=hp_atual_pct,
            hp_atualizado_em=pokemon.hp_atualizado_em,
        )


class PokemonDetalhe(PokemonResumo):
    """A ficha: os mesmos campos da lista, mais o que so faz sentido ao abrir um."""

    stats: StatsEfetivosLer
    hp_atual: int
    hp_maximo: int
    experiencia: int
    # Nulo no nivel maximo — nunca um numero enganoso, nunca zero (criterio 6).
    experiencia_para_proximo_nivel: int | None
    nivel_maximo: bool
    origem: str
    local_captura: str | None
    capturado_em: datetime | None
    treinador_nome: str | None


class PaginaPokemon(BaseModel):
    items: list[PokemonResumo]
    total: int
    page: int
    page_size: int
