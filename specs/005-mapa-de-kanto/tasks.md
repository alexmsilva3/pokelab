# 005 — Tarefas

| # | Tarefa | Agente | Verificação |
|---|---|---|---|
| 1 | `game/mapa.py`: alcance, estados e Dijkstra multi-origem | pokelab-domain | critérios 1 a 3, 5 |
| 2 | `game/mapa.py`: origem ótima e próximo passo | pokelab-domain | critérios 3, 4, 7 |
| 3 | `game/mapa.py`: duração estimada (SDD 4.4) | pokelab-domain | critério 7 |
| 4 | Modelo `PokedexAvistamento` e migração | pokelab-api | `upgrade` e `downgrade` |
| 5 | `GET /map` com estado, origem e duração | pokelab-api | critérios 1 a 5 |
| 6 | `GET /map/{id}` com avistamentos | pokelab-api | critérios 8 a 10 |
| 7 | Tela do mapa ordenada por distância | pokelab-frontend | critérios 1 a 4 |
| 8 | Detalhe do local com espécies avistadas | pokelab-frontend | critérios 8, 9 |
| 9 | Testes de backend dos doze critérios | pokelab-test | `make test-db` verde |
| 10 | Testes de frontend do mapa | pokelab-test | `npm run test` verde |
