.PHONY: help setup lint test build ci up down logs seed migrate revision shell-api clean

# O PokeLab roda lint e teste da API dentro de container, para nao depender do
# toolchain Python local. Se preferir rodar nativamente, instale python3-venv e
# use os alvos *-local.

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: ## Instala dependencias do frontend e prepara o .env
	@test -f .env || cp .env.example .env
	cd web && npm install

lint: ## Roda ruff e eslint
	ci/pipeline.sh lint

test: ## Roda pytest e vitest
	ci/pipeline.sh test

build: ## Constroi as imagens Docker
	ci/pipeline.sh build

ci: ## Pipeline completa: lint -> test -> build
	ci/pipeline.sh all

up: ## Sobe db + api + web
	docker compose up -d

down: ## Derruba os servicos
	docker compose down

logs: ## Acompanha os logs
	docker compose logs -f

shell-api: ## Shell dentro do container da API
	docker compose exec api sh

migrate: ## Aplica as migracoes
	docker compose exec api alembic upgrade head

revision: ## Cria migracao. Uso: make revision m="mensagem"
	docker compose exec api alembic revision --autogenerate -m "$(m)"

seed: ## Carrega data/seed/ no banco (Fase 1)
	@echo "Fase 1 ainda nao implementada"

lint-local: ## Lint sem Docker (exige api/.venv e web/node_modules)
	cd api && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests
	cd web && npm run lint

test-local: ## Testes sem Docker
	cd api && .venv/bin/pytest -q
	cd web && npm run test -- --run

clean:
	rm -rf api/.venv api/.pytest_cache api/.ruff_cache web/node_modules web/dist
