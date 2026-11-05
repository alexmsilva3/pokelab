"""Contrato de `/auth/register`, `/auth/login` e `/me` (spec 002, secao 5.3 do SDD).

Entrada e saida sao classes separadas (Artigo II): nenhum campo que o servidor
deriva aparece no schema de entrada, e nenhum schema de saida herda de um
modelo ORM nem carrega senha ou hash.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.game.laboratorio import limite_treinadores

# Bcrypt trunca silenciosamente alem de 72 bytes; o limite aqui evita que o
# professor digite uma senha maior achando que ela conta inteira.
TAMANHO_MAXIMO_SENHA = 72

# --- Entrada -----------------------------------------------------------------


class RegistroEntrada(BaseModel):
    usuario: str = Field(min_length=3, max_length=50)
    senha: str = Field(min_length=8, max_length=TAMANHO_MAXIMO_SENHA)
    nome_exibicao: str | None = Field(default=None, max_length=80)
    nome_laboratorio: str | None = Field(default=None, max_length=80)

    @field_validator("usuario", "nome_exibicao", "nome_laboratorio")
    @classmethod
    def _sem_espacos_nas_pontas(cls, valor: str | None) -> str | None:
        """Apara e recusa o que sobrar vazio.

        `min_length` valida a string crua, entao "   " passava e era gravado
        vazio depois da normalizacao.
        """
        if valor is None:
            return None
        aparado = valor.strip()
        if not aparado:
            raise ValueError("nao pode ser composto apenas por espacos")
        return aparado


class LoginEntrada(BaseModel):
    usuario: str = Field(min_length=1)
    senha: str = Field(min_length=1)


# --- Saida ---------------------------------------------------------------


class ProfessorLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario: str
    nome_exibicao: str
    criado_em: datetime


class LaboratorioLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    nivel: int
    experiencia: int
    moedas: int
    # Derivado do nivel pelo dominio e enviado pronto: o cliente nao recalcula
    # regra de jogo (Artigo II).
    limite_treinadores: int

    @classmethod
    def de_modelo(cls, laboratorio: object) -> LaboratorioLer:
        """Monta a saida acrescentando o que o dominio deriva do nivel."""
        return cls(
            id=laboratorio.id,
            nome=laboratorio.nome,
            nivel=laboratorio.nivel,
            experiencia=laboratorio.experiencia,
            moedas=laboratorio.moedas,
            limite_treinadores=limite_treinadores(laboratorio.nivel),
        )


class ResumoLer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    pokemon: int
    treinadores: int
    locais_desbloqueados: int
    especies_vistas: int
    especies_capturadas: int


class SessaoLer(BaseModel):
    token: str
    professor: ProfessorLer
    laboratorio: LaboratorioLer


class PerfilLer(BaseModel):
    professor: ProfessorLer
    laboratorio: LaboratorioLer
    resumo: ResumoLer
