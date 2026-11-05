# 001 — Tarefas

| # | Tarefa | Agente | Verificação |
|---|---|---|---|
| 1 | `tools/ingest_pokeapi.py`: espécies 1–151 da PokeAPI para `data/seed/species.json`, com cache | pokelab-data | roda duas vezes, segundo diff vazio |
| 2 | Sprites de frente e costas para `data/sprites/` | pokelab-data | 302 arquivos PNG presentes |
| 3 | Evolução por nível na ingestão, com alvo restrito aos 151 | pokelab-data | Charmander aponta para Charmeleon em Nv.16 |
| 4 | `data/seed/locations.json`: dez locais com grafo recíproco | pokelab-architect | teste de alcançabilidade passa |
| 5 | `data/seed/encounters.json`: pool por local com pesos | pokelab-data | nenhum pool vazio, nenhuma espécie órfã |
| 6 | `data/seed/items.json`: bolas, curas e revive | pokelab-data | seis itens carregados |
| 7 | Modelos de referência e migração | pokelab-api | `alembic upgrade head` e `downgrade base` funcionam |
| 8 | `app/seed.py` e alvo `make seed`, idempotente | pokelab-api | carregar duas vezes não muda contagem |
| 9 | Testes de integridade do acervo | pokelab-test | `make test` verde |
