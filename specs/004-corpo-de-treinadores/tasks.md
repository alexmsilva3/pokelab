# 004 — Tarefas

| # | Tarefa | Agente | Verificação |
|---|---|---|---|
| 1 | `game/power.py`: poder do Pokémon e do time (SDD 4.3) | pokelab-domain | tabela de valores conhecidos |
| 2 | `game/team.py`: invariantes 1–6 e 11, e capacidade de bagagem | pokelab-domain | cada invariante com teste |
| 3 | `game/trainers.py`: curva de nível e ganho de um terço por batalha | pokelab-domain | critério 9 |
| 4 | `GET /trainers` e `GET /trainers/{id}` | pokelab-api | critérios 1, 7, 8 |
| 5 | `PUT /trainers/{id}/team` com lock e transação | pokelab-api | critérios 2–6, 11 |
| 6 | `POST /trainers/{id}/team/preview` | pokelab-api | critério 9 |
| 7 | Filtro `livre` em `GET /pokemon` | pokelab-api | Pokémon de entrega fora |
| 8 | Lista de treinadores com status e time | pokelab-frontend | critério 1 |
| 9 | Montagem de time com prévia ao vivo | pokelab-frontend | critérios 2, 3, 7, 8 |
| 10 | Testes de backend dos doze critérios, mais concorrência | pokelab-test | `make test-db` verde |
| 11 | Testes de frontend da montagem | pokelab-test | `npm run test` verde |
