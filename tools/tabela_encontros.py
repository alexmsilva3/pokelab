#!/usr/bin/env python3
"""Gera docs/encontros.md a partir de data/seed/.

A tabela de encontros e uma decisao de game design que precisa ser lida e
discutida, nao so executada. Este script mantem a versao legivel em sincronia
com a fonte, para que nenhuma das duas minta.

Os pesos de cada local somam 100 por convencao, entao o peso le-se direto como
porcentagem de aparicao. O teste test_pesos_de_cada_local_somam_cem garante isso.

Uso:
    python3 tools/tabela_encontros.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
DIR_SEED = RAIZ / "data" / "seed"
DESTINO = RAIZ / "docs" / "encontros.md"

MINUTOS_POR_ENCONTRO = 3  # espelha balance.py; conferido por teste


def _ler(nome: str) -> Any:
    return json.loads((DIR_SEED / nome).read_text(encoding="utf-8"))


def montar() -> str:
    especies = {e["id"]: e for e in _ler("species.json")}
    locais = {local["id"]: local for local in _ler("locations.json")}
    encontros = _ler("encounters.json")

    linhas: list[str] = [
        "# Tabela de encontros",
        "",
        "Gerado por `tools/tabela_encontros.py` a partir de `data/seed/`. Não edite à mão:",
        "altere `encounters.json` ou `locations.json` e rode o script de novo.",
        "",
        "O peso de cada espécie é a porcentagem de aparecer num encontro daquele local —",
        "os pesos de um local somam 100 por convenção. Quantos encontros uma expedição gera",
        "é `encontros_base` do destino, independente de quanto tempo a viagem leva.",
        "",
        "## Resumo dos locais",
        "",
        "| Local | Tipo | Dificuldade | Nível selvagem | Encontros | Travessia | Espécies |",
        "|---|---|---|---|---|---|---|",
    ]

    ordem = sorted(locais.values(), key=lambda x: (x["nivel_dificuldade"], x["id"]))
    for local in ordem:
        pool = encontros.get(local["id"], [])
        linhas.append(
            f"| {local['nome']} | {local['tipo'].capitalize()} | {local['nivel_dificuldade']} "
            f"| {local['nivel_selvagem_min']}–{local['nivel_selvagem_max']} "
            f"| {local['encontros_base']} | {local['custo_travessia_minutos']} min "
            f"| {len(pool)} |"
        )

    for local in ordem:
        pool = sorted(encontros.get(local["id"], []), key=lambda p: (-p["peso"], p["especie_id"]))
        total = sum(p["peso"] for p in pool)

        linhas += [
            "",
            f"## {local['nome']}",
            "",
            f"{local['tipo'].capitalize()}, dificuldade {local['nivel_dificuldade']}, "
            f"{local['encontros_base']} encontros por expedição, "
            f"travessia de {local['custo_travessia_minutos']} min.",
            "",
            "| # | Pokémon | Tipo | Peso | Nível | Taxa de captura |",
            "|---|---|---|---|---|---|",
        ]

        for entrada in pool:
            especie = especies[entrada["especie_id"]]
            tipos = especie["tipo_primario"]
            if especie["tipo_secundario"]:
                tipos += f" / {especie['tipo_secundario']}"
            nivel = (
                str(entrada["nivel_min"])
                if entrada["nivel_min"] == entrada["nivel_max"]
                else f"{entrada['nivel_min']}–{entrada['nivel_max']}"
            )
            pct = 100 * entrada["peso"] / total
            linhas.append(
                f"| {especie['id']:03d} | {especie['nome']} | {tipos} "
                f"| **{pct:.0f}%** | {nivel} | {especie['taxa_captura']} |"
            )

        # Quantas expedições, em média, até ver cada espécie ao menos uma vez.
        encontros_por_ida = local["encontros_base"]
        raras = [p for p in pool if 100 * p["peso"] / total <= 10]
        if raras:
            linhas += ["", "Espécies raras deste local:", ""]
            for entrada in raras:
                especie = especies[entrada["especie_id"]]
                p = entrada["peso"] / total
                p_ida = 1 - (1 - p) ** encontros_por_ida
                idas = 1 / p_ida if p_ida else float("inf")
                linhas.append(
                    f"- **{especie['nome']}**: {100 * p_ida:.0f}% de aparecer por expedição, "
                    f"cerca de {idas:.0f} expedições até a primeira vez."
                )

    return "\n".join(linhas) + "\n"


def main() -> None:
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(montar(), encoding="utf-8")
    print(f"gerado {DESTINO.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
