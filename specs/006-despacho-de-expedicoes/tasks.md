# 006 — Tarefas

| # | Tarefa | Agente | Verificação |
|---|---|---|---|
| 1 | `game/expedition.py`: dificuldade e chance estimada (SDD 4.3) | pokelab-domain | tabela de valores |
| 2 | `game/expedition.py`: `calcular_despacho` com os invariantes 1, 2, 3, 6, 9 e 17 | pokelab-domain | critérios 2 a 4, 8 |
| 3 | `game/expedition.py`: `estado_observado` e `tempo_restante`, com o agora como parâmetro | pokelab-domain | critérios 9 e 11 |
| 4 | Modelos `Expedicao`, `ExpedicaoItem`, `ExpedicaoEvento` e migração | pokelab-api | `upgrade` e `downgrade` |
| 5 | `POST /expeditions` com lock e débito condicional | pokelab-api | critérios 1 a 8, 14 |
| 6 | `GET /expeditions` e `GET /expeditions/{id}` | pokelab-api | critérios 9 a 11, 13 |
| 7 | `DELETE /expeditions/{id}` | pokelab-api | critério 12 |
| 8 | `POST /expeditions/preview` | pokelab-api | prévia e despacho concordam |
| 9 | Tela de despacho com prévia | pokelab-frontend | critérios 1 a 4 |
| 10 | Painel de ativas com contador corrigido pelo servidor | pokelab-frontend | critérios 9 e 10 |
| 11 | Testes de backend dos catorze critérios, mais concorrência | pokelab-test | `make test-db` verde |
| 12 | Testes de frontend do despacho e do contador | pokelab-test | `npm run test` verde |
