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
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.referencia import Item, Local, PokemonEspecie


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

    # Nenhuma coluna nova: so o lado inverso de `PokemonInstancia.treinador_id`,
    # que ja existe desde a Fase 2. `back_populates` com `PokemonInstancia.treinador`
    # e o que deixa `selectinload`/`joinedload` buscarem o time inteiro com a
    # especie junta numa unica consulta extra (spec 004, secao 4 do plano).
    time: Mapped[list[PokemonInstancia]] = relationship(
        "PokemonInstancia", back_populates="treinador", order_by="PokemonInstancia.id"
    )

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

    # Relacionamentos de leitura para a ficha e a listagem (spec 003). Lazy
    # "select" por padrao: quem lista em volume usa `joinedload`/`selectinload`
    # explicito no repositorio, para nao reintroduzir o N+1 que esses mesmos
    # campos existem para evitar.
    especie: Mapped[PokemonEspecie] = relationship(PokemonEspecie)
    treinador: Mapped[Treinador | None] = relationship(Treinador, back_populates="time")
    local_captura: Mapped[Local | None] = relationship(Local)

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


class PokedexAvistamento(Base):
    """Onde cada especie de um laboratorio ja apareceu (SDD 3.2, spec 005).

    A Fase 5 so le esta tabela pelo mapa (`GET /map/{id}`, regra 9 da spec
    005): nenhum endpoint desta fase escreve nela. Quem grava e a tarefa 7.10,
    na descarga da Pokedex ao fim de cada expedicao. A tabela nasce agora, e
    nao isolada na Fase 7, porque o mapa precisa de algo para consultar e a
    migracao sai de graca junto das outras.

    Chave composta em vez de surrogate, como `LocalEncontro` e `ItemEstoque`:
    o par (laboratorio, especie, local) e naturalmente unico, e um id proprio
    so acrescentaria uma coluna sem significado.
    """

    __tablename__ = "pokedex_avistamentos"
    __table_args__ = (
        # GET /map/{id} filtra por laboratorio e local, nunca por especie
        # isolada: o prefixo (laboratorio_id, local_id) e o que essa consulta
        # usa, e a chave primaria sozinha (laboratorio_id, especie_id,
        # local_id) nao cobre esse prefixo.
        Index("ix_pokedex_avistamentos_laboratorio_local", "laboratorio_id", "local_id"),
    )

    laboratorio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("laboratorios.id"), primary_key=True
    )
    especie_id: Mapped[int] = mapped_column(ForeignKey("pokemon_especies.id"), primary_key=True)
    local_id: Mapped[str] = mapped_column(String(50), ForeignKey("locais.id"), primary_key=True)

    primeiro_visto_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vezes_visto: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    especie: Mapped[PokemonEspecie] = relationship()

    def __repr__(self) -> str:
        return f"<PokedexAvistamento {self.laboratorio_id}/{self.local_id}/{self.especie_id}>"


class Expedicao(Base):
    """Uma missao despachada, em curso ou ja concluida (SDD 3.2, spec 006).

    `status` guarda so o que e fato gravado: `EM_CURSO`, `CONCLUIDA_SUCESSO`,
    `CONCLUIDA_FALHA`, `ABORTADA`. `AGUARDANDO_RELATORIO` nao e valor de
    coluna — e derivado comparando `eta` com o relogio a cada leitura, em
    `game.expedition.estado_observado`. Gravar essa transicao exigiria um job
    varrendo o banco, e o ADR-004 decidiu nao ter um.

    Sem coluna para o caminho percorrido: origem e destino bastam para a Fase
    7 recalcular dificuldade e encontros, e o SDD 3.2 nao lista mais colunas
    que estas.
    """

    __tablename__ = "expedicoes"
    __table_args__ = (
        # GET /expeditions filtra sempre por laboratorio e quase sempre por
        # status — e a consulta mais frequente da tela (plan.md da spec 006).
        # Cobre tambem "so laboratorio_id", pelo prefixo, sem precisar de um
        # segundo indice.
        Index("ix_expedicoes_laboratorio_status", "laboratorio_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    laboratorio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("laboratorios.id"), nullable=False
    )
    treinador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("treinadores.id"), nullable=False
    )
    local_destino_id: Mapped[str] = mapped_column(ForeignKey("locais.id"), nullable=False)
    local_origem_id: Mapped[str] = mapped_column(ForeignKey("locais.id"), nullable=False)

    # EM_CURSO | CONCLUIDA_SUCESSO | CONCLUIDA_FALHA | ABORTADA (SDD 3.2)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="EM_CURSO")

    # A semente desta expedicao (ADR-005, invariante 13). BigInteger porque
    # balance.SEED_MAXIMO e o teto de um inteiro de 64 bits com sinal.
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    eta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Nulo ate a Fase 7 resolver: uma expedicao em curso, ou ja terminada e
    # aguardando relatorio, ainda nao tem resultado gravado.
    resolvida_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    duracao_minutos: Mapped[int] = mapped_column(Integer, nullable=False)
    # Gravadas com a mesma precisao que o professor viu no envio
    # (game.expedition.dificuldade_do_local/chance_estimada): a Fase 7 vai
    # resolver os encontros a partir destas colunas, e um relatorio com um
    # numero diferente do que foi mostrado no despacho nao explicaria o
    # proprio resultado.
    dificuldade_calculada: Mapped[float] = mapped_column(Float, nullable=False)
    poder_time_calculado: Mapped[float] = mapped_column(Float, nullable=False)

    treinador: Mapped[Treinador] = relationship(Treinador)
    local_destino: Mapped[Local] = relationship(Local, foreign_keys=[local_destino_id])
    local_origem: Mapped[Local] = relationship(Local, foreign_keys=[local_origem_id])
    itens: Mapped[list[ExpedicaoItem]] = relationship(
        "ExpedicaoItem", back_populates="expedicao", order_by="ExpedicaoItem.item_id"
    )
    eventos: Mapped[list[ExpedicaoEvento]] = relationship(
        "ExpedicaoEvento", back_populates="expedicao", order_by="ExpedicaoEvento.ordem"
    )

    def __repr__(self) -> str:
        return f"<Expedicao {self.id} status={self.status}>"


class ExpedicaoItem(Base):
    """A carga de uma expedicao: o que foi levado e o que ja foi gasto (SDD 3.2).

    Chave composta em vez de surrogate, como `ItemEstoque`: o par
    (expedicao, item) e naturalmente unico, e um id proprio so acrescentaria
    uma coluna sem significado.
    """

    __tablename__ = "expedicao_itens"

    expedicao_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expedicoes.id"), primary_key=True
    )
    item_id: Mapped[str] = mapped_column(ForeignKey("itens.id"), primary_key=True)

    quantidade_levada: Mapped[int] = mapped_column(Integer, nullable=False)
    # Zero ate a Fase 7 consumir Pocoes e Revives durante a resolucao.
    quantidade_consumida: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    expedicao: Mapped[Expedicao] = relationship(Expedicao, back_populates="itens")
    item: Mapped[Item] = relationship(Item)

    def __repr__(self) -> str:
        return f"<ExpedicaoItem {self.expedicao_id}/{self.item_id}={self.quantidade_levada}>"


class ExpedicaoEvento(Base):
    """Uma linha do relatorio de campo (SDD 3.2).

    Nasce vazia nesta fase: quem preenche e a Fase 7, na resolucao. A tabela
    existe desde ja para nao exigir uma migracao isolada depois, mesmo padrao
    de `PokedexAvistamento` na Fase 5.
    """

    __tablename__ = "expedicao_eventos"
    __table_args__ = (
        # A Fase 7 le os eventos de uma expedicao sempre em ordem; a
        # unicidade impede duas linhas disputando o mesmo lugar na timeline
        # se a resolucao um dia rodar duas vezes por engano (Artigo VII).
        Index("ix_expedicao_eventos_expedicao_ordem", "expedicao_id", "ordem", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    expedicao_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("expedicoes.id"), nullable=False
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)

    # PARTIDA | BATALHA | CAPTURA | CAPTURA_FALHA | DESCOBERTA | ITEM |
    # CONTRATEMPO | SUBIU_NIVEL | EVOLUCAO | RETORNO (SDD 3.2)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    texto: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    ocorrido_em_minuto: Mapped[int] = mapped_column(Integer, nullable=False)

    expedicao: Mapped[Expedicao] = relationship(Expedicao, back_populates="eventos")

    def __repr__(self) -> str:
        return f"<ExpedicaoEvento {self.id} expedicao={self.expedicao_id} tipo={self.tipo}>"
