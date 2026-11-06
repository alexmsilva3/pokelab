# 007 — Tarefas

| # | Tarefa | Agente | Verificação |
|---|---|---|---|
| 1 | `game/experience.py`: aplicar ganho, subir nível com teto 100 e descartar excedente | pokelab-domain | critérios 9, 10, 12 |
| 2 | `game/evolucao.py`: cadeia de evolução por nível, com teto de iterações | pokelab-domain | critério 11 |
| 3 | `game/capture.py`: `p_captura` e slots de bagagem (SDD 4.6) | pokelab-domain | critérios 6, 7, 8 |
| 4 | `game/encounter.py`: sorteio ponderado de espécie e nível, interface do resolvedor (ADR-003) | pokelab-domain | critério 3 |
| 5 | `game/cura.py`: escolha e efeito do item de cura, reinício da contagem de derrotas | pokelab-domain | critérios 15, 16 |
| 6 | `game/achados.py`: tabela ponderada de itens e quantidade por dificuldade (SDD 7.12) | pokelab-domain | evento `ITEM` no relatório |
| 7 | `game/expedition.py::resolver`: laço de encontros na ordem fixada, eventos ordenados, status final | pokelab-domain | critérios 1, 3, 15 |
| 8 | Textos narrativos em português por tipo de evento, com interpolação | pokelab-domain | revisão de texto |
| 9 | `game/stats.py::hp_recuperado`: recuperação passiva derivada do relógio | pokelab-domain | critérios 20, 21 |
| 10 | Constantes novas em `balance.py` com nome, unidade e motivo | pokelab-domain | Artigo IV |
| 11 | Coluna `hp_atualizado_em` e migração com `downgrade` | pokelab-api | `make migrate` ida e volta |
| 12 | Materialização do HP recuperado no despacho | pokelab-api | critério 21 |
| 13 | `POST /expeditions/{id}/claim` com lock, checagem de status e escrita completa | pokelab-api | critérios 1, 2, 4, 5, 22 |
| 14 | Escrita do resultado: capturas, HP do time, Pokédex, avistamentos, desbloqueio, estoque, treinador livre | pokelab-api | critérios 6, 7, 13, 17, 18 |
| 15 | EXP de treinador e de laboratório com subida de nível | pokelab-api | critérios 9, 14 |
| 16 | Relatório no `GET /expeditions/{id}` e schemas do relatório | pokelab-api | critério 19 |
| 17 | HP derivado nas leituras de Pokémon e de treinador | pokelab-api | critério 20 |
| 18 | Tela de relatório: linha do tempo, capturas, três experiências, itens | pokelab-frontend | critério 19 |
| 19 | Botão de receber relatório no painel de expedições | pokelab-frontend | critérios 1, 2 |
| 20 | Testes de determinismo por semente e de ordem dos sorteios | pokelab-test | critério 3 |
| 21 | Testes de idempotência e concorrência do claim | pokelab-test | critérios 4, 5 |
| 22 | Testes de bagagem cheia, sem bola e de falha por três derrotas | pokelab-test | critérios 7, 8, 15, 16 |
| 23 | Testes de Pokédex, avistamento e desbloqueio | pokelab-test | critérios 13, 17, 18 |
| 24 | Testes de frontend do relatório | pokelab-test | critério 19 |
