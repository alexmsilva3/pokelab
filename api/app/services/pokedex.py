"""Caso de uso da Pokedex do laboratorio (spec 003).

So monta o envelope a partir do que o repositorio ja combinou. Nao ha regra
de jogo aqui: o unico cuidado e nao deixar o nome de uma especie desconhecida
atravessar para o schema errado (criterio 9), e isso e decisao de forma, nao
de calculo.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.repositories import pokedex as pokedex_repo
from app.repositories.pokedex import LinhaPokedex
from app.schemas.pokedex import (
    EntradaPokedex,
    EntradaPokedexCapturada,
    EntradaPokedexDesconhecida,
    EntradaPokedexVista,
    PokedexLer,
)


def _tipos(linha: LinhaPokedex) -> list[str]:
    tipos = [linha.especie.tipo_primario]
    if linha.especie.tipo_secundario:
        tipos.append(linha.especie.tipo_secundario)
    return tipos


def _entrada(linha: LinhaPokedex) -> EntradaPokedex:
    if linha.capturado:
        return EntradaPokedexCapturada(
            numero=linha.especie.id,
            nome=linha.especie.nome,
            tipos=_tipos(linha),
            sprite=linha.especie.sprite_frente,
            quantidade=linha.quantidade,
        )
    if linha.visto:
        return EntradaPokedexVista(
            numero=linha.especie.id,
            nome=linha.especie.nome,
            tipos=_tipos(linha),
            sprite=linha.especie.sprite_frente,
        )
    return EntradaPokedexDesconhecida(numero=linha.especie.id)


def listar(sessao: Session, laboratorio_id: uuid.UUID) -> PokedexLer:
    linhas = pokedex_repo.listar_entradas(sessao, laboratorio_id)
    return PokedexLer(
        items=[_entrada(linha) for linha in linhas],
        capturadas=sum(1 for linha in linhas if linha.capturado),
        vistas=sum(1 for linha in linhas if linha.visto),
    )
