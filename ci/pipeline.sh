#!/usr/bin/env bash
#
# Pipeline do PokeLab: lint -> test -> build.
#
# Este script e a fonte da verdade do CI. O arquivo de workflow da plataforma
# (GitHub Actions, Azure Pipelines, GitLab CI) e apenas um invocador de tres
# linhas que chama daqui, para que trocar de host nao reescreva a verificacao.
#
# Uso: ci/pipeline.sh [lint|test|test-db|test-arquivos <alvos>|build|all]

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
  docker run --rm -v "$RAIZ:/src" -w /src/api "$(imagem_de_teste)" \
    sh -c "ruff check app tests ../tools && ruff format --check app tests ../tools"

  info "lint: eslint (web)"
  docker run --rm -v "$RAIZ/web:/src" -w /src node:24-alpine \
    sh -c "$(comando_node 'npm run lint')"
}

test_suite() {
  info "test: pytest (api)"
  # O repositorio inteiro e montado porque os testes de integridade leem
  # data/seed/ e data/sprites/. Os testes de carga pulam sozinhos sem Postgres.
  docker run --rm -v "$RAIZ:/src" -w /src/api "$(imagem_de_teste)" pytest -q

  info "test: vitest (web)"
  docker run --rm -v "$RAIZ/web:/src" -w /src node:24-alpine \
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

  docker run --rm --network "$rede" -v "$RAIZ:/src" -w /src/api \
    -e POSTGRES_HOST=db \
    -e POSTGRES_USER="$POSTGRES_USER" \
    -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    -e POSTGRES_DB="$POSTGRES_DB" \
    "$(imagem_de_teste)" pytest -q
}

# Subconjunto da suite, com Postgres quando ele estiver de pe. Existe para que
# um agente conferindo o proprio modulo nao precise rodar as mil e tantas.
test_arquivos() {
  local alvos="$*"
  [ -n "$alvos" ] || { echo "uso: ci/pipeline.sh test-arquivos tests/test_x.py" >&2; exit 2; }

  local rede args
  rede="$(docker network ls --format '{{.Name}}' | grep -E 'pokelab.*default' | head -1)"
  args=(--rm -v "$RAIZ:/src" -w /src/api)

  if [ -n "$rede" ] && [ -f "$RAIZ/.env" ]; then
    # shellcheck disable=SC1091
    set -a; . "$RAIZ/.env"; set +a
    args+=(--network "$rede" -e POSTGRES_HOST=db \
      -e POSTGRES_USER="$POSTGRES_USER" \
      -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
      -e POSTGRES_DB="$POSTGRES_DB")
  fi

  info "test: $alvos"
  # shellcheck disable=SC2086
  docker run "${args[@]}" "$(imagem_de_teste)" pytest -q $alvos
}

build() {
  info "build: imagens docker"
  cd "$RAIZ" && docker compose build
}

case "$ETAPA" in
  lint)  lint ;;
  test)  test_suite ;;
  test-db) test_db ;;
  test-arquivos) shift; test_arquivos "$@" ;;
  build) build ;;
  all)   lint && test_suite && build ;;
  *)     echo "etapa desconhecida: $ETAPA" >&2; exit 2 ;;
esac

info "pipeline concluida"
