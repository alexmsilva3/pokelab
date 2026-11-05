"""Carga das tabelas de referencia a partir de data/seed/.

Idempotente por decisao de projeto: o seed faz upsert por chave natural, nunca
truncate-insert, porque a partida do professor referencia estas linhas.

Uso:
    python -m app.seed
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Item, Local, LocalEncontro, PokemonEspecie

# Em container o seed e montado em /data; fora dele, esta na raiz do repositorio.
_RAIZ_PADRAO = Path(__file__).resolve().parent.parent.parent / "data"
DIR_SEED = (Path("/data") if Path("/data").is_dir() else _RAIZ_PADRAO) / "seed"


def _ler(nome: str) -> Any:
    arquivo = DIR_SEED / nome
    if not arquivo.exists():
        raise SystemExit(f"arquivo de seed ausente: {arquivo}. Rode tools/ingest_pokeapi.py")
    return json.loads(arquivo.read_text(encoding="utf-8"))


def _aplicar(instancia: Any, dados: dict[str, Any], ignorar: set[str]) -> None:
    for chave, valor in dados.items():
        if chave not in ignorar:
            setattr(instancia, chave, valor)


def carregar_especies(sessao: Session) -> int:
    registros = _ler("species.json")
    existentes = {e.id: e for e in sessao.scalars(select(PokemonEspecie))}

    # Duas passadas: as evolucoes referenciam especies que podem ainda nao existir.
    for dados in registros:
        especie = existentes.get(dados["id"])
        if especie is None:
            especie = PokemonEspecie(id=dados["id"])
            sessao.add(especie)
            existentes[dados["id"]] = especie
        _aplicar(especie, dados, ignorar={"id", "evolui_para_id", "evolui_em_nivel"})
    sessao.flush()

    for dados in registros:
        especie = existentes[dados["id"]]
        especie.evolui_para_id = dados["evolui_para_id"]
        especie.evolui_em_nivel = dados["evolui_em_nivel"]
    sessao.flush()

    return len(registros)


def carregar_locais(sessao: Session) -> int:
    registros = _ler("locations.json")
    existentes = {local.id: local for local in sessao.scalars(select(Local))}

    for dados in registros:
        local = existentes.get(dados["id"])
        if local is None:
            local = Local(id=dados["id"])
            sessao.add(local)
        _aplicar(local, dados, ignorar={"id"})
    sessao.flush()

    return len(registros)


def carregar_encontros(sessao: Session) -> int:
    registros = _ler("encounters.json")
    existentes = {(e.local_id, e.especie_id): e for e in sessao.scalars(select(LocalEncontro))}

    vistos: set[tuple[str, int]] = set()
    total = 0
    for local_id, pool in registros.items():
        for dados in pool:
            chave = (local_id, dados["especie_id"])
            vistos.add(chave)
            total += 1
            encontro = existentes.get(chave)
            if encontro is None:
                encontro = LocalEncontro(local_id=local_id, especie_id=dados["especie_id"])
                sessao.add(encontro)
            encontro.peso = dados["peso"]
            encontro.nivel_min = dados["nivel_min"]
            encontro.nivel_max = dados["nivel_max"]

    # Encontro removido do JSON sai do banco: a tabela e espelho do seed, e
    # nenhuma linha de partida aponta para ela.
    for chave, encontro in existentes.items():
        if chave not in vistos:
            sessao.delete(encontro)

    sessao.flush()
    return total


def carregar_itens(sessao: Session) -> int:
    registros = _ler("items.json")
    existentes = {item.id: item for item in sessao.scalars(select(Item))}

    for dados in registros:
        item = existentes.get(dados["id"])
        if item is None:
            item = Item(id=dados["id"])
            sessao.add(item)
        _aplicar(item, dados, ignorar={"id"})
    sessao.flush()

    return len(registros)


def executar(sessao: Session) -> dict[str, int]:
    resumo = {
        "especies": carregar_especies(sessao),
        "locais": carregar_locais(sessao),
        "encontros": carregar_encontros(sessao),
        "itens": carregar_itens(sessao),
    }
    sessao.commit()
    return resumo


def main() -> None:
    with SessionLocal() as sessao:
        resumo = executar(sessao)
    for entidade, quantidade in resumo.items():
        print(f"{entidade}: {quantidade}", file=sys.stderr)


if __name__ == "__main__":
    main()
