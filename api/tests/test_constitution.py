"""Guarda automatizada do Artigo I: o dominio e puro.

Este teste existe para que a fronteira de app/game/ nao erode silenciosamente.
"""

import ast
from pathlib import Path

GAME_DIR = Path(__file__).resolve().parent.parent / "app" / "game"

IMPORTS_PROIBIDOS = {
    "sqlalchemy",
    "fastapi",
    "requests",
    "httpx",
    "alembic",
    "psycopg",
    "app.core",
    "app.models",
    "app.services",
    "app.repositories",
    "app.routers",
}

CHAMADAS_PROIBIDAS = {
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("time", "time"),
    ("os", "getenv"),
}


def _modulos_do_dominio() -> list[Path]:
    return sorted(GAME_DIR.rglob("*.py"))


def test_dominio_nao_importa_infraestrutura():
    infratores: list[str] = []
    for arquivo in _modulos_do_dominio():
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            nomes: list[str] = []
            if isinstance(no, ast.Import):
                nomes = [alias.name for alias in no.names]
            elif isinstance(no, ast.ImportFrom) and no.module:
                nomes = [no.module]
            for nome in nomes:
                if any(nome == p or nome.startswith(p + ".") for p in IMPORTS_PROIBIDOS):
                    infratores.append(f"{arquivo.name}: import {nome}")
    assert not infratores, "Artigo I violado: " + "; ".join(infratores)


def test_dominio_nao_le_o_relogio_nem_o_ambiente():
    infratores: list[str] = []
    for arquivo in _modulos_do_dominio():
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call) or not isinstance(no.func, ast.Attribute):
                continue
            alvo = no.func.value
            if isinstance(alvo, ast.Name) and (alvo.id, no.func.attr) in CHAMADAS_PROIBIDAS:
                infratores.append(f"{arquivo.name}: {alvo.id}.{no.func.attr}()")
    assert not infratores, "Artigo I violado: " + "; ".join(infratores)


def test_dominio_nao_usa_random_global():
    infratores: list[str] = []
    for arquivo in _modulos_do_dominio():
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                for alias in no.names:
                    if alias.name == "random":
                        infratores.append(f"{arquivo.name}: import random")
            elif isinstance(no, ast.ImportFrom) and no.module == "random":
                infratores.append(f"{arquivo.name}: from random import ...")
    assert not infratores, (
        "Artigo III violado: use um gerador semeado recebido como parametro. "
        + "; ".join(infratores)
    )
