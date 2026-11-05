#!/usr/bin/env bash
#
# Pipeline do PokeLab: lint -> test -> build.
#
# Este script e a fonte da verdade do CI. O arquivo de workflow da plataforma
# (GitHub Actions, Azure Pipelines, GitLab CI) e apenas um invocador de tres
# linhas que chama daqui, para que trocar de host nao reescreva a verificacao.
#
# Uso: ci/pipeline.sh [lint|test|test-db|build|all]

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ETAPA="${1:-all}"

info() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

lint() {
  info "lint: ruff (api)"
  docker run --rm -v "$RAIZ:/src" -w /src/api python:3.12-slim \
    sh -c "pip install -q ruff && ruff check app tests ../tools && ruff format --check app tests ../tools"

  info "lint: eslint (web)"
  docker run --rm -v "$RAIZ/web:/src" -w /src node:24-alpine \
    sh -c "npm ci --silent && npm run lint"
}

test_suite() {
  info "test: pytest (api)"
  # O repositorio inteiro e montado porque os testes de integridade leem
  # data/seed/ e data/sprites/. Os testes de carga pulam sozinhos sem Postgres.
  docker run --rm -v "$RAIZ:/src" -w /src/api python:3.12-slim \
    sh -c "pip install -q -e '.[dev]' && pytest -q"

  info "test: vitest (web)"
  docker run --rm -v "$RAIZ/web:/src" -w /src node:24-alpine \
    sh -c "npm ci --silent && npm run test -- --run"
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
  docker run --rm --network "$rede" -v "$RAIZ:/src" -w /src/api \
    -e POSTGRES_HOST=db \
    -e POSTGRES_USER="$POSTGRES_USER" \
    -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
    -e POSTGRES_DB="$POSTGRES_DB" \
    python:3.12-slim sh -c "pip install -q -e '.[dev]' && pytest -q"
}

build() {
  info "build: imagens docker"
  cd "$RAIZ" && docker compose build
}

case "$ETAPA" in
  lint)  lint ;;
  test)  test_suite ;;
  test-db) test_db ;;
  build) build ;;
  all)   lint && test_suite && build ;;
  *)     echo "etapa desconhecida: $ETAPA" >&2; exit 2 ;;
esac

info "pipeline concluida"
