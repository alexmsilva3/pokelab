"""Modelos das tabelas de referencia do PokeLab.

Artigo V da constituicao: estas tabelas sao preenchidas pelo seed e imutaveis em
runtime. Nenhum endpoint escreve nelas.

Chave natural em vez de surrogate: o seed precisa ser idempotente entre
maquinas, e um id auto-incremento divergiria entre instalacoes.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PokemonEspecie(Base):
    __tablename__ = "pokemon_especies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    nome: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    tipo_primario: Mapped[str] = mapped_column(String(20), nullable=False)
    tipo_secundario: Mapped[str | None] = mapped_column(String(20))

    hp_base: Mapped[int] = mapped_column(Integer, nullable=False)
    ataque_base: Mapped[int] = mapped_column(Integer, nullable=False)
    defesa_base: Mapped[int] = mapped_column(Integer, nullable=False)
    ataque_especial_base: Mapped[int] = mapped_column(Integer, nullable=False)
    defesa_especial_base: Mapped[int] = mapped_column(Integer, nullable=False)
    velocidade_base: Mapped[int] = mapped_column(Integer, nullable=False)

    experiencia_base: Mapped[int] = mapped_column(Integer, nullable=False)
    taxa_captura: Mapped[int] = mapped_column(Integer, nullable=False)
    curva_crescimento: Mapped[str] = mapped_column(String(20), nullable=False)

    evolui_para_id: Mapped[int | None] = mapped_column(ForeignKey("pokemon_especies.id"))
    evolui_em_nivel: Mapped[int | None] = mapped_column(Integer)

    sprite_frente: Mapped[str] = mapped_column(String(50), nullable=False)
    sprite_costas: Mapped[str] = mapped_column(String(50), nullable=False)
    e_inicial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    @property
    def soma_stats_base(self) -> int:
        return (
            self.hp_base
            + self.ataque_base
            + self.defesa_base
            + self.ataque_especial_base
            + self.defesa_especial_base
            + self.velocidade_base
        )

    def __repr__(self) -> str:
        return f"<PokemonEspecie {self.id} {self.nome}>"


class Local(Base):
    __tablename__ = "locais"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), nullable=False)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)

    nivel_dificuldade: Mapped[int] = mapped_column(Integer, nullable=False)
    nivel_selvagem_min: Mapped[int] = mapped_column(Integer, nullable=False)
    nivel_selvagem_max: Mapped[int] = mapped_column(Integer, nullable=False)
    duracao_base_minutos: Mapped[int] = mapped_column(Integer, nullable=False)

    # Dez locais com arestas fixas, sempre lidos inteiros: uma tabela de juncao
    # custaria um join em toda consulta de mapa sem ganho nenhum.
    vizinhos: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    e_inicial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    encontros: Mapped[list[LocalEncontro]] = relationship(back_populates="local")

    def __repr__(self) -> str:
        return f"<Local {self.id}>"


class LocalEncontro(Base):
    __tablename__ = "local_encontros"

    local_id: Mapped[str] = mapped_column(ForeignKey("locais.id"), primary_key=True)
    especie_id: Mapped[int] = mapped_column(ForeignKey("pokemon_especies.id"), primary_key=True)

    peso: Mapped[int] = mapped_column(Integer, nullable=False)
    nivel_min: Mapped[int] = mapped_column(Integer, nullable=False)
    nivel_max: Mapped[int] = mapped_column(Integer, nullable=False)

    local: Mapped[Local] = relationship(back_populates="encontros")
    especie: Mapped[PokemonEspecie] = relationship()

    def __repr__(self) -> str:
        return f"<LocalEncontro {self.local_id}/{self.especie_id}>"


class Item(Base):
    __tablename__ = "itens"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    nome: Mapped[str] = mapped_column(String(80), nullable=False)
    categoria: Mapped[str] = mapped_column(String(20), nullable=False)

    potencia: Mapped[float] = mapped_column(Float, nullable=False)
    efeito_duracao: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    def __repr__(self) -> str:
        return f"<Item {self.id}>"
