# 003 — Tarefas

| # | Tarefa | Agente | Verificação |
|---|---|---|---|
| 1 | `game/stats.py`: stats efetivos e HP absoluto (SDD 4.2), puros | pokelab-domain | tabela de valores conhecidos |
| 2 | `repositories/pokemon.py`: listagem com filtros, paginação e join único | pokelab-api | teste que conta consultas |
| 3 | `GET /pokemon` com os filtros combináveis | pokelab-api | critérios 2, 3 e 4 |
| 4 | `GET /pokemon/{id}` com stats efetivos e EXP para o próximo nível | pokelab-api | critérios 5 e 6 |
| 5 | `PATCH /pokemon/{id}` para apelido, com limpeza por nulo | pokelab-api | critério 7 |
| 6 | `GET /pokedex` com as três formas de entrada | pokelab-api | critérios 8 e 9 |
| 7 | `GET /items` sem itens zerados | pokelab-api | critério 11 |
| 8 | Sprites em `/sprites` com cache imutável | pokelab-infra | critério 12 |
| 9 | Lista, filtros e cartões no laboratório | pokelab-frontend | critérios 1 a 4 |
| 10 | Ficha lateral com stats, EXP e origem | pokelab-frontend | critérios 5 a 7 |
| 11 | Tela da Pokédex com as três aparências | pokelab-frontend | critérios 8 e 9 |
| 12 | Painel de mochila | pokelab-frontend | critério 11 |
| 13 | Testes de backend dos doze critérios | pokelab-test | `make test-db` verde |
| 14 | Testes de frontend das telas novas | pokelab-test | `npm run test` verde |
