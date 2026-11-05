# 002 — Tarefas

| # | Tarefa | Agente | Verificação |
|---|---|---|---|
| 1 | `game/experience.py`: as quatro curvas de crescimento, puras e testadas | pokelab-domain | tabela de valores conhecidos passa |
| 2 | `game/trainers.py`: nome e avatar determinísticos a partir de gerador semeado | pokelab-domain | mesmo seed, mesmo nome |
| 3 | `game/kit_inicial.py`: descrição do kit, sem I/O | pokelab-domain | devolve 3 starters nv.5, 1 treinador, estoque, local |
| 4 | Modelos de estado e migração única | pokelab-api | `upgrade` e `downgrade` funcionam |
| 5 | Hash de senha e emissão/validação de JWT em `core/seguranca.py` | pokelab-api | token inválido rejeitado |
| 6 | `services/auth.py`: registro atômico com kit, e login | pokelab-api | transação única, idempotente |
| 7 | Rotas `/auth/register`, `/auth/login`, `/me` | pokelab-api | contratos do plano respeitados |
| 8 | Dependência `professor_atual` e envelope de erro uniforme | pokelab-api | 401 sem token, 404 cruzado |
| 9 | Cliente HTTP com Authorization e tratamento de 401 | pokelab-frontend | 401 limpa sessão e redireciona |
| 10 | Telas de Login e Registro, store de sessão, rota protegida | pokelab-frontend | sessão sobrevive ao reload |
| 11 | Tela do laboratório consumindo `/me` | pokelab-frontend | mostra nível, moedas e contagens |
| 12 | Testes de backend cobrindo os onze critérios de aceite | pokelab-test | `make test-db` verde |
| 13 | Testes de frontend das telas novas | pokelab-test | `npm run test` verde |
