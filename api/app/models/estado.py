"""Modelos das tabelas de estado do PokeLab (spec 002).

Ao contrario das tabelas de referencia (`referencia.py`), estas sao escritas em
runtime, uma por professor/laboratorio. UUID como chave primaria em vez de
inteiro sequencial: o id aparece em URL, e sequencial convida a enumerar o
laboratorio do vizinho (regra 12 da spec 002).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Professor(Base):
    __tablename__ = "professores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # `usuario` preserva a grafia escolhida no registro; `usuario_normalizado`
    # e a mesma string em minusculas e carrega a unicidade. Uma coluna
    # normalizada em vez de indice funcional em lower(usuario) porque toda
    # consulta de login compara contra uma coluna simples, sem envolver
    # `func.lower()` em cada repositorio que procura um professor.
    usuario: Mapped[str] = mapped_column(String(50), nullable=False)
    usuario_normalizado: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nome_exibicao: Mapped[str] = mapped_column(String(80), nullable=False)

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ultimo_acesso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Professor {self.id} {self.usuario}>"


class Laboratorio(Base):
    __tablename__ = "laboratorios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Unique: e assim que "um laboratorio por conta" (regra 5 da spec 002)
    # vira regra de banco, resistente a concorrencia.
    professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professores.id"), nullable=False, unique=True
    )

    nome: Mapped[str] = mapped_column(String(80), nullable=False)
    nivel: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    experiencia: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    moedas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Invariante 10 do SDD 3.3: os starters sao concedidos exatamente uma vez.
    starters_concedidos: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Semente usada para montar o kit inicial. Guardada para que o kit de
    # qualquer laboratorio possa ser remontado identico (Artigo III).
    semente_kit_inicial: Mapped[int | None] = mapped_column(BigInteger)

    # Carimbo do ultimo sorteio da lista de entregas (Fase 8, invariante 15).
    entregas_geradas_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<Laboratorio {self.id} {self.nome}>"


class Treinador(Base):
    __tablename__ = "treinadores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    laboratorio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("laboratorios.id"), nullable=False, index=True
    )

    nome: Mapped[str] = mapped_column(String(50), nullable=False)
    # {"iniciais": "AL", "cor": "#1f7a3f"} — forma que Avatar.para_dicionario() produz.
    avatar: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)

    nivel: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    experiencia: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # DISPONIVEL | EM_EXPEDICAO | EM_ENTREGA | DESCANSANDO (SDD 3.2)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DISPONIVEL")

    expedicoes_concluidas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    entregas_concluidas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<Treinador {self.id} {self.nome}>"


class PokemonInstancia(Base):
    __tablename__ = "pokemon_instancias"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    laboratorio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("laboratorios.id"), nullable=False, index=True
    )
    especie_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pokemon_especies.id"), nullable=False
    )

    apelido: Mapped[str | None] = mapped_column(String(50))
    nivel: Mapped[int] = mapped_column(Integer, nullable=False)
    experiencia: Mapped[int] = mapped_column(Integer, nullable=False)
    hp_atual_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    # Nulo = esta no laboratorio, fora de qualquer time (invariante 2 do SDD 3.3).
    treinador_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("treinadores.id")
    )

    # INICIAL | CAPTURADO | EVOLUCAO (SDD 3.2)
    origem: Mapped[str] = mapped_column(String(20), nullable=False)
    local_captura_id: Mapped[str | None] = mapped_column(String(50), ForeignKey("locais.id"))
    capturado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # `comprometido_entrega_id` do SDD 3.2 entra na Fase 8, junto da tabela
    # `entregas`: nao ha o que referenciar ainda.

    def __repr__(self) -> str:
        return f"<PokemonInstancia {self.id} especie={self.especie_id}>"


class ItemEstoque(Base):
    __tablename__ = "item_estoques"

    laboratorio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("laboratorios.id"), primary_key=True
    )
    item_id: Mapped[str] = mapped_column(ForeignKey("itens.id"), primary_key=True)

    quantidade: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return f"<ItemEstoque {self.laboratorio_id}/{self.item_id}={self.quantidade}>"


class LocalDesbloqueado(Base):
    __tablename__ = "locais_desbloqueados"

    laboratorio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("laboratorios.id"), primary_key=True
    )
    local_id: Mapped[str] = mapped_column(ForeignKey("locais.id"), primary_key=True)

    desbloqueado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<LocalDesbloqueado {self.laboratorio_id}/{self.local_id}>"


class PokedexEntrada(Base):
    __tablename__ = "pokedex_entradas"

    laboratorio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("laboratorios.id"), primary_key=True
    )
    especie_id: Mapped[int] = mapped_column(ForeignKey("pokemon_especies.id"), primary_key=True)

    visto: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    capturado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    primeiro_visto_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<PokedexEntrada {self.laboratorio_id}/{self.especie_id}>"
