#!/usr/bin/env python3
"""Ingestor de dados do PokeLab.

Baixa as 151 primeiras especies da PokeAPI e os sprites do repositorio publico
PokeAPI/sprites, normaliza para o schema da secao 3.1 do SDD e grava em
data/seed/ e data/sprites/ — versionados no repositorio.

Artigo V da constituicao: a aplicacao em execucao nunca chama a PokeAPI. Este
script roda fora dela, por decisao humana, e o que importa e o diff que ele
produz.

Usa apenas a stdlib de proposito: o ingestor nao deve arrastar dependencia para
dentro de api/.

Uso:
    python3 tools/ingest_pokeapi.py            # usa cache quando existir
    python3 tools/ingest_pokeapi.py --sem-cache
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
DIR_SEED = RAIZ / "data" / "seed"
DIR_SPRITES = RAIZ / "data" / "sprites"
DIR_CACHE = RAIZ / "data" / "cache"

POKEAPI = "https://pokeapi.co/api/v2"
SPRITES_BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon"

PRIMEIRA_ESPECIE = 1
ULTIMA_ESPECIE = 151
PAUSA_SEGUNDOS = 0.05
TENTATIVAS = 3

INICIAIS = {1, 4, 7}  # Bulbasaur, Charmander, Squirtle

# A PokeAPI nomeia os stats assim; o SDD usa os nomes abaixo.
MAPA_STATS = {
    "hp": "hp_base",
    "attack": "ataque_base",
    "defense": "defesa_base",
    "special-attack": "ataque_especial_base",
    "special-defense": "defesa_especial_base",
    "speed": "velocidade_base",
}

# A PokeAPI usa slugs; estes quatro nomes nao sobrevivem a um capitalize().
NOMES_ESPECIAIS = {
    "nidoran-f": "Nidoran\u2640",
    "nidoran-m": "Nidoran\u2642",
    "mr-mime": "Mr. Mime",
    "farfetchd": "Farfetch'd",
}

MAPA_CURVAS = {
    "fast": "rapida",
    "medium": "media_rapida",
    "medium-slow": "media_lenta",
    "slow": "lenta",
    "slow-then-very-fast": "lenta",  # inexistente nos 151, mapeado por seguranca
    "fast-then-very-slow": "rapida",
}


def log(mensagem: str) -> None:
    print(mensagem, file=sys.stderr, flush=True)


def _baixar(url: str) -> bytes:
    ultimo_erro: Exception | None = None
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            requisicao = urllib.request.Request(url, headers={"User-Agent": "PokeLab-ingest/0.1"})
            with urllib.request.urlopen(requisicao, timeout=30) as resposta:
                return resposta.read()
        except (urllib.error.URLError, TimeoutError) as erro:
            ultimo_erro = erro
            espera = tentativa * 2
            log(f"  falha ({erro}), nova tentativa em {espera}s")
            time.sleep(espera)
    raise RuntimeError(f"nao foi possivel baixar {url}") from ultimo_erro


def buscar_json(url: str, usar_cache: bool = True) -> dict[str, Any]:
    """Busca um recurso JSON, com cache em disco indexado pelo caminho da url."""
    chave = url.replace(f"{POKEAPI}/", "").strip("/").replace("/", "_") + ".json"
    arquivo = DIR_CACHE / chave

    if usar_cache and arquivo.exists():
        return json.loads(arquivo.read_text(encoding="utf-8"))

    conteudo = _baixar(url)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_bytes(conteudo)
    time.sleep(PAUSA_SEGUNDOS)
    return json.loads(conteudo)


def baixar_sprite(especie_id: int, lado: str, usar_cache: bool = True) -> bool:
    """Baixa um sprite. Devolve False quando a fonte nao tem aquele lado."""
    sufixo = "" if lado == "front" else "back/"
    url = f"{SPRITES_BASE}/{sufixo}{especie_id}.png"
    destino = DIR_SPRITES / f"{especie_id}-{lado}.png"

    if usar_cache and destino.exists() and destino.stat().st_size > 0:
        return True

    try:
        conteudo = _baixar(url)
    except RuntimeError:
        log(f"  sprite ausente: {especie_id}-{lado}")
        return False

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(conteudo)
    time.sleep(PAUSA_SEGUNDOS)
    return True


def _id_da_url(url: str) -> int:
    return int(url.rstrip("/").split("/")[-1])


def extrair_evolucao(cadeia: dict[str, Any]) -> dict[int, tuple[int, int]]:
    """Percorre uma cadeia de evolucao e devolve {origem_id: (destino_id, nivel)}.

    Apenas evolucoes por nivel entram. Pedra, troca e amizade ficam de fora da v1
    (fora de escopo da spec 001) e produzem evolui_para_id nulo.
    """
    evolucoes: dict[int, tuple[int, int]] = {}

    def visitar(no: dict[str, Any]) -> None:
        origem_id = _id_da_url(no["species"]["url"])
        for seguinte in no.get("evolves_to", []):
            destino_id = _id_da_url(seguinte["species"]["url"])
            for detalhe in seguinte.get("evolution_details", []):
                gatilho = (detalhe.get("trigger") or {}).get("name")
                nivel = detalhe.get("min_level")
                if gatilho == "level-up" and nivel:
                    evolucoes[origem_id] = (destino_id, int(nivel))
                    break
            visitar(seguinte)

    visitar(cadeia)
    return evolucoes


def normalizar_especie(
    pokemon: dict[str, Any],
    especie: dict[str, Any],
    evolucao: tuple[int, int] | None,
) -> dict[str, Any]:
    tipos = sorted(pokemon["types"], key=lambda t: t["slot"])
    stats = {
        MAPA_STATS[s["stat"]["name"]]: s["base_stat"]
        for s in pokemon["stats"]
        if s["stat"]["name"] in MAPA_STATS
    }

    curva_origem = especie["growth_rate"]["name"]
    if curva_origem not in MAPA_CURVAS:
        raise ValueError(f"curva de crescimento desconhecida: {curva_origem}")

    especie_id = pokemon["id"]
    return {
        "id": especie_id,
        "nome": NOMES_ESPECIAIS.get(pokemon["name"], pokemon["name"].capitalize()),
        "tipo_primario": tipos[0]["type"]["name"],
        "tipo_secundario": tipos[1]["type"]["name"] if len(tipos) > 1 else None,
        **stats,
        "experiencia_base": pokemon["base_experience"],
        "taxa_captura": especie["capture_rate"],
        "curva_crescimento": MAPA_CURVAS[curva_origem],
        "evolui_para_id": evolucao[0] if evolucao else None,
        "evolui_em_nivel": evolucao[1] if evolucao else None,
        "sprite_frente": f"{especie_id}-front.png",
        "sprite_costas": f"{especie_id}-back.png",
        "e_inicial": especie_id in INICIAIS,
    }


def gravar_json(caminho: Path, conteudo: Any) -> None:
    """Grava com chaves ordenadas e indentacao fixa, para o diff ser legivel."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(conteudo, indent=2, ensure_ascii=False, sort_keys=True)
    caminho.write_text(texto + "\n", encoding="utf-8")


def ingerir(usar_cache: bool = True) -> list[dict[str, Any]]:
    cadeias: dict[str, dict[int, tuple[int, int]]] = {}
    especies: list[dict[str, Any]] = []
    sprites_ausentes: list[str] = []

    for especie_id in range(PRIMEIRA_ESPECIE, ULTIMA_ESPECIE + 1):
        pokemon = buscar_json(f"{POKEAPI}/pokemon/{especie_id}", usar_cache)
        dados_especie = buscar_json(f"{POKEAPI}/pokemon-species/{especie_id}", usar_cache)

        url_cadeia = dados_especie["evolution_chain"]["url"]
        if url_cadeia not in cadeias:
            cadeia = buscar_json(url_cadeia, usar_cache)
            cadeias[url_cadeia] = extrair_evolucao(cadeia["chain"])

        evolucao = cadeias[url_cadeia].get(especie_id)
        # Evolucao para fora dos 151 nao existe na v1.
        if evolucao and evolucao[0] > ULTIMA_ESPECIE:
            evolucao = None

        especies.append(normalizar_especie(pokemon, dados_especie, evolucao))

        for lado in ("front", "back"):
            if not baixar_sprite(especie_id, lado, usar_cache):
                sprites_ausentes.append(f"{especie_id}-{lado}")

        if especie_id % 25 == 0:
            log(f"  {especie_id}/{ULTIMA_ESPECIE}")

    if sprites_ausentes:
        log(f"sprites ausentes: {', '.join(sprites_ausentes)}")

    return sorted(especies, key=lambda e: e["id"])


def validar(especies: list[dict[str, Any]]) -> None:
    """Checagens obrigatorias da skill pokelab-data-seed, antes de gravar."""
    erros: list[str] = []
    ids = {e["id"] for e in especies}

    if len(especies) != ULTIMA_ESPECIE:
        erros.append(f"esperadas {ULTIMA_ESPECIE} especies, obtidas {len(especies)}")

    faltando = set(range(PRIMEIRA_ESPECIE, ULTIMA_ESPECIE + 1)) - ids
    if faltando:
        erros.append(f"ids ausentes: {sorted(faltando)}")

    obrigatorios = (
        "nome",
        "tipo_primario",
        "hp_base",
        "ataque_base",
        "defesa_base",
        "ataque_especial_base",
        "defesa_especial_base",
        "velocidade_base",
        "experiencia_base",
        "taxa_captura",
        "curva_crescimento",
    )
    for especie in especies:
        for campo in obrigatorios:
            if especie.get(campo) in (None, ""):
                erros.append(f"especie {especie['id']}: campo obrigatorio '{campo}' vazio")
        alvo = especie["evolui_para_id"]
        if alvo is not None:
            if alvo not in ids:
                erros.append(f"especie {especie['id']}: evolui para {alvo}, fora dos 151")
            if not especie["evolui_em_nivel"]:
                erros.append(f"especie {especie['id']}: evolui sem nivel definido")

    iniciais = [e["id"] for e in especies if e["e_inicial"]]
    if sorted(iniciais) != sorted(INICIAIS):
        erros.append(f"iniciais incorretos: {iniciais}")

    if erros:
        for erro in erros:
            log(f"ERRO {erro}")
        raise SystemExit(f"validacao falhou com {len(erros)} erro(s)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingestor de dados do PokeLab")
    parser.add_argument(
        "--sem-cache",
        action="store_true",
        help="ignora data/cache/ e rebaixa tudo da PokeAPI",
    )
    argumentos = parser.parse_args()

    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    DIR_SPRITES.mkdir(parents=True, exist_ok=True)

    log(f"ingerindo especies {PRIMEIRA_ESPECIE} a {ULTIMA_ESPECIE} da PokeAPI")
    especies = ingerir(usar_cache=not argumentos.sem_cache)

    log("validando")
    validar(especies)

    gravar_json(DIR_SEED / "species.json", especies)
    com_evolucao = sum(1 for e in especies if e["evolui_para_id"])
    log(
        f"gravado data/seed/species.json: {len(especies)} especies, "
        f"{com_evolucao} com evolucao por nivel"
    )


if __name__ == "__main__":
    main()
