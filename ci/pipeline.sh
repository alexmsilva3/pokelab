#!/usr/bin/env bash
#
# Pipeline do PokeLab: lint -> test -> build.
#
# Este script e a fonte da verdade do CI. O arquivo de workflow da plataforma
# (GitHub Actions, Azure Pipelines, GitLab CI) e apenas um invocador de tres
# linhas que chama daqui, para que trocar de host nao reescreva a verificacao.
#
# Uso: ci/pipeline.sh [lint|test|test-db|test-arquivos <alvos>|build|limpar|all]

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ETAPA="${1:-all}"

info() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

# Imagem com as dependencias de teste ja instaladas.
#
# Antes, cada invocacao rodava `pip install -e '.[dev]'` do zero: 1m43 de
# espera antes do primeiro teste. Com varios agentes rodando a suite algumas
# vezes cada, isso somava dezenas de minutos por fase — mais tempo instalando
# do que testando. Com a imagem pronta, o mesmo comando leva 3 segundos.
#
# A tag carrega o hash do pyproject.toml: mudou dependencia, a tag muda e a
# imagem se reconstroi sozinha. Enquanto nao muda, nada e reconstruido.
imagem_de_teste() {
  local hash tag
  hash="$(sha256sum "$RAIZ/api/pyproject.toml" | cut -c1-12)"
  tag="pokelab-test:$hash"
  if ! docker image inspect "$tag" >/dev/null 2>&1; then
    # Em stderr: esta funcao e chamada dentro de $(...), e qualquer byte em
    # stdout viraria parte do nome da imagem.
    info "preparando a imagem de teste (so quando pyproject.toml muda)" >&2
    docker build -q -t "$tag" -f "$RAIZ/api/Dockerfile.test" "$RAIZ/api" >/dev/null 2>&1
  fi
  printf '%s' "$tag"
}

# --- Ciclo de vida dos containers de teste --------------------------------
#
# `docker run --rm` remove o container quando ele TERMINA. Nao cobre o caso em
# que o container nao termina, nem o caso em que quem o lancou morre antes
# dele: o daemon e o dono, e o processo que chamou `docker run` ir embora nao
# derruba nada.
#
# Foi assim que apareceram oito containers pendurados, alguns por duas horas,
# segurando locks no Postgres e fazendo a suite levar dez vezes mais.
#
# Tres defesas: nome previsivel (da para achar e matar), teto de tempo (trava
# vira falha em minutos, nao em horas) e trap de saida (sair por qualquer
# motivo leva o container junto).

# A suite roda num banco PROPRIO, nunca no da aplicacao.
#
# Ate aqui ela usava o mesmo POSTGRES_DB do .env, e o TRUNCATE que o
# conftest da entre cada teste levava junto a conta de desenvolvimento, o
# laboratorio e os Pokemon de quem estivesse jogando. O sintoma chegava como
# 401 no login, tres vezes, sem nenhuma pista de que a culpa era da suite.
#
# O banco de teste e criado e migrado por `preparar_banco_de_teste` na
# primeira vez que faz falta; depois disso e so mais um banco no mesmo
# Postgres.
banco_de_teste() { printf '%s_teste' "$POSTGRES_DB"; }

preparar_banco_de_teste() {
  local banco; banco="$(banco_de_teste)"
  if docker compose exec -T db psql -U "$POSTGRES_USER" -d postgres -tAc \
       "SELECT 1 FROM pg_database WHERE datname='$banco';" 2>/dev/null | grep -q 1; then
    return 0
  fi
  info "criando o banco de teste $banco" >&2
  docker compose exec -T db createdb -U "$POSTGRES_USER" "$banco" >/dev/null
  docker run --rm --network "$1" -v "$RAIZ:/src" -w /src/api \
    -e POSTGRES_HOST=db -e POSTGRES_USER="$POSTGRES_USER" \
    -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" -e POSTGRES_DB="$banco" \
    -e SECRET_KEY="$SECRET_KEY" -e ENVIRONMENT=development \
    "$(imagem_de_teste)" sh -c 'alembic upgrade head && python -m app.seed' >/dev/null 2>&1
}

PREFIXO_CONTAINER="pokelab_teste"
# Teto por execucao. A suite completa leva ~90s; cinco minutos e folga generosa
# e ainda assim curto o bastante para uma trava nao virar problema de horas.
# Teto por container de teste. Os 300s iniciais foram calibrados quando a suite
# levava 90; hoje leva 165 em maquina livre, e a margem caiu de 3x para menos de
# 2x sem ninguem notar. Com a maquina disputada por agentes, a suite passou dos
# 300 e foi derrubada — falso negativo que parece falha de teste. 600 devolve a
# margem; se um dia a suite encostar nisso, o problema e a suite, nao o teto.
TIMEOUT_TESTE_SEGUNDOS="${TIMEOUT_TESTE_SEGUNDOS:-600}"

_containers_desta_execucao=()

# Remove o que esta execucao criou, aconteca o que acontecer com o script.
limpar_containers() {
  local nome
  for nome in "${_containers_desta_execucao[@]:-}"; do
    [ -n "$nome" ] && docker rm -f "$nome" >/dev/null 2>&1 || true
  done
  _containers_desta_execucao=()
}
trap limpar_containers EXIT INT TERM

# Containers de execucoes anteriores que ficaram para tras. Roda antes de
# comecar, porque e justamente o lixo antigo que segura o lock do banco.
# Containers da imagem de teste que escaparam do prefixo.
#
# `limpar_orfaos` so alcanca quem nasceu com o nome PREFIXO_CONTAINER. Um agente
# que monte `docker run --name outra_coisa` com a imagem de teste fica de fora, e
# ja aconteceu: um laco arquivo-a-arquivo ficou vivo depois do workflow terminar,
# disputando CPU e banco com a suite seguinte. O sintoma foi a suite levar 900s
# em vez de 165 e ser derrubada pelo timeout — um falso negativo que parece
# falha de teste.
limpar_por_imagem() {
  local imagem; imagem="$(imagem_de_teste 2>/dev/null)" || return 0
  local id nome
  for id in $(docker ps -q --filter "ancestor=$imagem" 2>/dev/null); do
    nome="$(docker inspect -f '{{.Name}}' "$id" 2>/dev/null | sed 's#^/##')"
    # Os desta execucao ja estao no trap; estes sao de outra, que terminou sem
    # limpar. Comparar por NOME, nao por lista: lista vazia com `grep -v` casa
    # com tudo e apagaria os proprios containers em uso.
    case "$nome" in
      "${PREFIXO_CONTAINER}"*) continue ;;
    esac
    info "removendo container de teste orfao: $nome" >&2
    docker rm -f "$id" >/dev/null 2>&1 || true
  done
}

limpar_orfaos() {
  local antigos
  antigos="$(docker ps -q --filter "name=^${PREFIXO_CONTAINER}" 2>/dev/null)"
  [ -n "$antigos" ] || return 0
  info "removendo containers de teste de execucoes anteriores" >&2
  # shellcheck disable=SC2086
  docker rm -f $antigos >/dev/null 2>&1 || true
}

# Um `docker run` que nao deixa rastro: nome proprio, teto de tempo e remocao
# garantida pelo trap.
rodar_container() {
  local nome status
  nome="${PREFIXO_CONTAINER}_$$_${#_containers_desta_execucao[@]}"
  _containers_desta_execucao+=("$nome")

  status=0
  timeout --signal=TERM --kill-after=20s "$TIMEOUT_TESTE_SEGUNDOS" \
    docker run --name "$nome" --rm "$@" || status=$?

  if [ "$status" -eq 124 ] || [ "$status" -eq 137 ]; then
    echo "container de teste passou de ${TIMEOUT_TESTE_SEGUNDOS}s e foi derrubado" >&2
  fi
  docker rm -f "$nome" >/dev/null 2>&1 || true
  return "$status"
}

# node_modules do host, quando existe, em vez de `npm ci` a cada execucao.
# Host e container sao Linux x64, entao os binarios nativos servem aos dois.
comando_node() {
  if [ -d "$RAIZ/web/node_modules" ]; then
    printf '%s' "$1"
  else
    printf 'npm ci --silent && %s' "$1"
  fi
}

lint() {
  info "lint: ruff (api)"
  rodar_container -v "$RAIZ:/src" -w /src/api "$(imagem_de_teste)" \
    sh -c "ruff check app tests ../tools && ruff format --check app tests ../tools"

  info "lint: eslint (web)"
  rodar_container -v "$RAIZ/web:/src" -w /src node:24-alpine \
    sh -c "$(comando_node 'npm run lint')"
}

test_suite() {
  info "test: pytest (api)"
  # O repositorio inteiro e montado porque os testes de integridade leem
  # data/seed/ e data/sprites/. Os testes de carga pulam sozinhos sem Postgres.
  rodar_container -v "$RAIZ:/src" -w /src/api "$(imagem_de_teste)" pytest -q

  info "test: vitest (web)"
  rodar_container -v "$RAIZ/web:/src" -w /src node:24-alpine \
    sh -c "$(comando_node 'npm run test -- --run')"
}

# Testes que exigem Postgres. Os testes de carga do seed pulam sozinhos quando
# o banco nao esta acessivel, entao esta etapa e separada e opcional no CI.
test_db() {
  info "test: pytest com Postgres (api)"
  local rede
  rede="$(docker network ls --format '{{.Name}}' | grep -E 'pokelab.*default' | head -1)"
  if [ -z "$rede" ]; then
    echo "docker compose nao esta de pe; rode 'make up' antes" >&2
    exit 1
  fi
  # shellcheck disable=SC1091
  set -a; . "$RAIZ/.env"; set +a

  # Uma execucao por vez.
  #
  # O conftest da TRUNCATE nas tabelas de estado entre testes, entao duas
  # suites contra o mesmo banco se bloqueiam: ja apareceram oito containers
  # pendurados por horas. Banco por execucao seria melhor, mas `createdb -T`
  # exige ninguem conectado ao template, e a API esta.
  #
  # Esperar a vez e previsivel; travar nao e. Agentes que querem conferir so o
  # proprio modulo devem usar `make test-arquivos`, que nao disputa este lock.
  exec 9>"$RAIZ/.pytest.lock"
  if ! flock -n 9; then
    info "outra suite esta rodando; aguardando a vez"
    flock 9
  fi

  preparar_banco_de_teste "$rede"

  rodar_container --network "$rede" -v "$RAIZ:/src" -w /src/api \
    -e POSTGRES_HOST=db \
    -e POSTGRES_USER="$POSTGRES_USER" \
    -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    -e POSTGRES_DB="$(banco_de_teste)" \
    "$(imagem_de_teste)" pytest -q
}

# Subconjunto da suite, com Postgres quando ele estiver de pe. Existe para que
# um agente conferindo o proprio modulo nao precise rodar as mil e tantas.
test_arquivos() {
  local alvos="$*"
  [ -n "$alvos" ] || { echo "uso: ci/pipeline.sh test-arquivos tests/test_x.py" >&2; exit 2; }

  local rede args
  rede="$(docker network ls --format '{{.Name}}' | grep -E 'pokelab.*default' | head -1)"
  args=(-v "$RAIZ:/src" -w /src/api)

  if [ -n "$rede" ] && [ -f "$RAIZ/.env" ]; then
    # shellcheck disable=SC1091
    set -a; . "$RAIZ/.env"; set +a
    preparar_banco_de_teste "$rede"
    args+=(--network "$rede" -e POSTGRES_HOST=db \
      -e POSTGRES_USER="$POSTGRES_USER" \
      -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
      -e POSTGRES_DB="$(banco_de_teste)")
  fi

  info "test: $alvos"
  # shellcheck disable=SC2086
  rodar_container "${args[@]}" "$(imagem_de_teste)" pytest -q $alvos
}

build() {
  info "build: imagens docker"
  cd "$RAIZ" && docker compose build
}

limpar_orfaos
limpar_por_imagem

case "$ETAPA" in
  limpar) info "limpeza concluida"; exit 0 ;;
  lint)  lint ;;
  test)  test_suite ;;
  test-db) test_db ;;
  test-arquivos) shift; test_arquivos "$@" ;;
  build) build ;;
  all)   lint && test_suite && build ;;
  *)     echo "etapa desconhecida: $ETAPA" >&2; exit 2 ;;
esac

info "pipeline concluida"
