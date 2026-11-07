# 008 — Tarefas

| # | Tarefa | Agente | Verificação |
|---|---|---|---|
| 1 | `game/viveiro.py`: `CAPACIDADE_VIVEIRO`, ocupação e transbordo | pokelab-domain | critérios 1 a 3 |
| 2 | Guarda do despacho com viveiro transbordado, e só nele | pokelab-domain | critérios 4 e 5 |
| 3 | Evento de bagagem cheia no relatório, sem consumir sorteio | pokelab-domain | critério 31 |
| 4 | `game/soltar.py`: invariantes 24 e 25 | pokelab-domain | critérios 9 a 11 |
| 5 | `game/delivery.py`: banda de raridade por nível e filtro de alcançável | pokelab-domain | critérios 13 a 17 |
| 6 | Prazo da oferta: `EXPIRADA` derivada, função única | pokelab-domain | critérios 18 a 20 |
| 7 | Duração e recompensas da entrega | pokelab-domain | critério 27 |
| 8 | Modelos `Entrega`, `EntregaRequisito`, `comprometido_entrega_id` e migração | pokelab-api | `upgrade` e `downgrade` |
| 9 | `GET /ranch` e ocupação no resumo do laboratório | pokelab-api | critérios 1 e 2 |
| 10 | `DELETE /pokemon/{id}` | pokelab-api | critérios 6 a 12 |
| 11 | `GET /deliveries` com estado observado e vagas | pokelab-api | critérios 18 e 22 |
| 12 | `POST /deliveries/refresh` com as duas semânticas | pokelab-api | critérios 21 e 22 |
| 13 | `POST /deliveries/{id}/accept` com os Pokémon escolhidos | pokelab-api | critérios 20, 23 a 26 |
| 14 | `POST /deliveries/{id}/claim` idempotente sob lock | pokelab-api | critérios 27 a 30 |
| 15 | Recusa `VIVEIRO_TRANSBORDADO` no despacho | pokelab-api | critérios 4 e 5 |
| 16 | Tela do viveiro com ocupação, aviso de transbordo e soltar | pokelab-frontend | critérios 1 a 6 |
| 17 | Tela Central de Entregas com prazo, repor e regerar | pokelab-frontend | critérios 18, 21, 22 |
| 18 | Seleção dos Pokémon no aceite, com confirmação nomeada | pokelab-frontend | critérios 23 e 24 |
| 19 | Testes do viveiro e do soltar | pokelab-test | critérios 1 a 12 |
| 20 | Testes da geração e do prazo | pokelab-test | critérios 13 a 22 |
| 21 | Testes da entrega, com concorrência no claim | pokelab-test | critérios 23 a 32 |
| 22 | Testes de frontend das duas telas | pokelab-test | `npm run test` verde |
