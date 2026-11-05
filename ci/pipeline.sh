#!/usr/bin/env bash
#
# Pipeline do PokeLab: lint -> test -> build.
#
# Este script e a fonte da verdade do CI. O arquivo de workflow da plataforma
# (GitHub Actions, Azure Pipelines, GitLab CI) e apenas um invocador de tres
# linhas que chama daqui, para que trocar de host nao reescreva a verificacao.
#
# Uso: ci/pipeline.sh [lint|test|build|all]

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ETAPA="${1:-all}"

info() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

lint() {
  info "lint: ruff (api)"
  docker run --rm -v "$RAIZ/api:/src" -w /src python:3.12-slim \
    sh -c "pip install -q ruff && ruff check app tests && ruff format --check app tests"

  info "lint: eslint (web)"
  docker run --rm -v "$RAIZ/web:/src" -w /src node:24-alpine \
    sh -c "npm ci --silent && npm run lint"
}

test_suite() {
  info "test: pytest (api)"
  docker run --rm -v "$RAIZ/api:/src" -w /src python:3.12-slim \
    sh -c "pip install -q -e '.[dev]' && pytest -q"

  info "test: vitest (web)"
  docker run --rm -v "$RAIZ/web:/src" -w /src node:24-alpine \
    sh -c "npm ci --silent && npm run test -- --run"
}

build() {
  info "build: imagens docker"
  cd "$RAIZ" && docker compose build
}

case "$ETAPA" in
  lint)  lint ;;
  test)  test_suite ;;
  build) build ;;
  all)   lint && test_suite && build ;;
  *)     echo "etapa desconhecida: $ETAPA" >&2; exit 2 ;;
esac

info "pipeline concluida"
