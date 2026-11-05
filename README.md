# PokeLab

Jogo de gestão de navegador. O jogador é um **Professor Pokémon** que administra um laboratório: recebe três starters, recruta treinadores NPC, monta times de até três Pokémon e os despacha em **expedições** assíncronas pelo mapa de Kanto. As expedições correm em tempo real, resolvem no servidor e voltam com um relatório de campo — capturas, experiência, itens e locais desbloqueados.

Primeira versão: os 151 Pokémon originais, dez locais de Pallet a Cerulean, duas expedições simultâneas.

## Documentação

- [SDD.md](SDD.md) — especificação, decisões de arquitetura, modelo de domínio, regras de jogo e as dez fases do projeto.
- [specs/constitution.md](specs/constitution.md) — princípios invioláveis.

## Stack

FastAPI + PostgreSQL 16 no backend, React + Vite + TypeScript no frontend, Docker Compose para o ambiente local.

## Começando

```bash
cp .env.example .env
make setup
make up
```

API em `http://localhost:8000` (documentação em `/docs`), interface em `http://localhost:5173`.

Fora do Docker, `make lint` e `make test` rodam as verificações dos dois lados. `make help` lista o resto.

## Organização

```
api/app/game/   dominio puro: fórmulas, invariantes e constantes de balanceamento
api/app/        API, persistência e casos de uso
web/src/        interface
data/seed/      dados versionados dos 151, locais, encontros e itens
tools/          ingestão de dados e simulação de balanceamento
specs/          artefatos de spec-driven development
.claude/        agentes e skills do projeto
```

A regra que sustenta o resto: `api/app/game/` não importa banco, rede nem relógio.
