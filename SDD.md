# PokeLab — Documento de Especificação e Condução (SDD)

Versão 0.1 — 2026-11-05
Responsável: Alex Silva (professor / arquiteto / operador)
Método: Spec-Driven Development (especificação é a fonte da verdade; código é derivado dela)

---

## 1. Visão

PokeLab é um jogo de gestão de navegador no qual o jogador assume o papel de **Professor Pokémon** e administra um **Laboratório**. O jogador não batalha: ele recruta e equipa **Treinadores** (NPCs), monta times, e os envia em **Expedições** assíncronas pelo mapa de Kanto. As expedições rodam em tempo real, resolvem encontros no servidor e retornam com um relatório de campo: Pokémon capturados, experiência ganha, itens consumidos, locais desbloqueados.

A referência de loop é o sistema de frotas de *No Man's Sky*: despachar, esperar, receber resultado, reinvestir. A referência de dados é a primeira geração — **somente os 151 primeiros Pokémon na v1**.

### 1.1 O que a v1 entrega

- Tela de login (autenticação simplificada, sem federação).
- Laboratório como tela principal, com 3 starters concedidos na criação do perfil.
- Lista de Pokémon do laboratório, com detalhe por indivíduo.
- Treinadores NPC com time de até 3 Pokémon, atribuídos pelo professor.
- Recorte de Kanto com 10 locais (Pallet até Cerulean) e progressão por desbloqueio.
- Até 2 expedições simultâneas.
- Motor de expedição assíncrono com log narrativo de eventos.
- Pokédex (vistos / capturados).
- Mochila simples: Pokébolas, Poções, Revives.

### 1.2 O que a v1 não entrega (registrado para não virar escopo acidental)

Batalha interativa por turnos; troca entre jogadores; evolução por pedra/troca; criação/breeding (apesar do verbo "criar" na ideia original, aqui significa **treinar e desenvolver**, não reprodução); movimentos individuais e PP; status persistente de sono/paralisia; níveis de laboratório; som e animação; mobile nativo.

### 1.3 Glossário

| Termo | Significado no PokeLab |
|---|---|
| **Professor** | O jogador. Dono do laboratório. Nunca entra em campo. |
| **Laboratório** | Agregado raiz do jogador: Pokémon, treinadores, itens, progresso, slots de expedição. |
| **Treinador** | NPC empregado do laboratório. Possui nível próprio e um time de até 3 Pokémon. |
| **Time** | Até 3 instâncias de Pokémon atribuídas a um treinador. |
| **Local** | Cidade ou rota de Kanto. Nó do grafo do mapa. |
| **Expedição** | Missão assíncrona: um treinador, um local de destino, uma janela de tempo, um resultado. |
| **Encontro** | Evento aleatório dentro de uma expedição: batalha selvagem, descoberta, item ou contratempo. |
| **Relatório de campo** | Log de eventos gerado na resolução da expedição, apresentado ao professor no retorno. |
| **Desbloqueio** | Efeito de uma expedição bem-sucedida: o local vira ponto de partida válido para novas expedições. |

---

## 2. Decisões de arquitetura

Decisões fechadas. Mudá-las implica revisar as fases afetadas.

### ADR-001 — Stack: FastAPI + React (Vite) + PostgreSQL

Backend Python com FastAPI é a autoridade sobre regra de jogo, tempo e aleatoriedade. Frontend React (Vite, TypeScript) é cliente burro de uma API REST. PostgreSQL como persistência.

**Motivo:** o tempo da expedição e a rolagem de encontros precisam ser autoritativos no servidor — se o cliente decidir, o jogo é trivialmente burlável. Python dá o melhor ferramental para a ingestão de dados Pokémon e para scripts de balanceamento. A separação API/SPA encaixa diretamente no modelo de CI/CD já em uso (build Docker, Artifact Registry via WIF, deploy por `docker compose` em servidor fora da GCP).

**Consequência:** dois artefatos de build e dois jobs de lint (ruff + ESLint). Contrato entre eles é o OpenAPI gerado pelo FastAPI, com cliente TypeScript gerado a partir dele.

### ADR-002 — Dados e sprites: PokeAPI + repositório PokeAPI/sprites

Um script de ingestão baixa, de uma vez, espécies, tipos, stats-base, taxa de captura, experiência-base e curva de crescimento dos 151, e grava um **seed versionado** no repositório (JSON normalizado + sprites PNG). Em runtime a aplicação nunca chama a PokeAPI.

**Motivo:** reprodutibilidade de build, nenhuma dependência de rede em produção, nenhuma ROM no repositório, licenciamento claro dos assets.

**Consequência:** o repositório carrega alguns MB de sprites. A atualização de dados é um ato deliberado (rodar o ingestor e commitar o diff), não um efeito colateral de deploy.

### ADR-003 — Resolução de combate: probabilística com log narrativo

O servidor não simula turnos. Para cada encontro, compara o poder efetivo do time com a dificuldade do local, rola o resultado, e **emite um evento legível** ("Charmander derrotou Rattata Nv.4 — +52 EXP", "Pikachu escapou da Pokébola").

**Motivo:** entrega o loop completo com uma fração do esforço de uma engine de batalha, e o valor percebido está no relatório, não na mecânica turno a turno.

**Consequência:** a resolução fica atrás da interface `EncounterResolver`. Uma simulação de turnos real pode substituí-la numa versão futura sem tocar em expedição, treinador ou laboratório.

### ADR-004 — Tempo real, com aceleração em desenvolvimento

A expedição grava `started_at` e `eta` no banco. O progresso corre com o navegador fechado. A resolução é **preguiçosa e idempotente**: ao consultar uma expedição cujo `eta` já passou e que ainda está `EM_CURSO`, o servidor resolve, persiste e devolve o resultado — dentro de uma transação com lock na linha.

Uma variável de ambiente `EXPEDITION_TIME_SCALE` (padrão `1.0`) divide todas as durações. Em dev e em teste vale `0.01`, transformando 20 minutos em 12 segundos.

**Motivo:** mantém a fidelidade ao loop assíncrono sem exigir um worker/scheduler na v1, e sem tornar o desenvolvimento insuportável.

**Consequência:** a primeira leitura após o `eta` paga o custo da resolução. Aceitável na escala de um jogo de laboratório. Se virar problema, troca-se por um job periódico sem mudar o contrato da API.

### ADR-005 — Aleatoriedade semeada e reproduzível

Cada expedição recebe um `seed` inteiro no momento do envio. Toda rolagem usa um PRNG derivado desse seed. Resolver a mesma expedição duas vezes com o mesmo estado produz exatamente o mesmo relatório.

**Motivo:** torna bugs de balanceamento reproduzíveis, permite testes determinísticos e viabiliza simulações em massa para tuning.

---

## 3. Modelo de domínio

```
Professor (1) ── (1) Laboratorio
                      │
                      ├── (N) PokemonInstancia ──> (1) PokemonEspecie [seed]
                      ├── (N) Treinador ── (0..3) PokemonInstancia  [time]
                      ├── (N) ItemEstoque ──> (1) Item [seed]
                      ├── (N) LocalDesbloqueado ──> (1) Local [seed]
                      ├── (N) PokedexEntrada ──> (1) PokemonEspecie
                      └── (0..2) Expedicao ── (N) ExpedicaoEvento
                                   │
                                   ├──> (1) Treinador
                                   ├──> (1) Local (destino)
                                   └──> (N) ExpedicaoItem [carga]
```

### 3.1 Entidades de referência (seed, imutáveis em runtime)

**PokemonEspecie** — `id` (1..151), `nome`, `tipo_primario`, `tipo_secundario`, `hp_base`, `ataque_base`, `defesa_base`, `ataque_especial_base`, `defesa_especial_base`, `velocidade_base`, `experiencia_base`, `taxa_captura`, `curva_crescimento`, `evolui_para_id`, `evolui_em_nivel`, `sprite_frente`, `sprite_costas`, `e_inicial`.

**Local** — `id`, `nome`, `tipo` (`CIDADE` | `ROTA` | `MASMORRA`), `nivel_dificuldade` (1..10), `nivel_selvagem_min`, `nivel_selvagem_max`, `custo_travessia_minutos`, `encontros_base`, `vizinhos` (arestas do grafo), `e_inicial`.

**LocalEncontro** — `local_id`, `especie_id`, `peso` (probabilidade relativa), `nivel_min`, `nivel_max`.

**Item** — `id`, `nome`, `categoria` (`POKEBOLA` | `CURA` | `REVIVE`), `potencia`, `efeito_duracao` (modificador de tempo de expedição).

### 3.2 Entidades de estado

**Professor** — `id`, `usuario`, `senha_hash`, `nome_exibicao`, `criado_em`, `ultimo_acesso`.

**Laboratorio** — `id`, `professor_id`, `nome`, `nivel` (fixo em 1 na v1), `slots_expedicao` (fixo em 2 na v1), `starters_concedidos` (bool).

**PokemonInstancia** — `id`, `laboratorio_id`, `especie_id`, `apelido`, `nivel`, `experiencia`, `hp_atual_pct` (0..100, desgaste pós-expedição), `treinador_id` (nulo = está no laboratório), `origem` (`INICIAL` | `CAPTURADO` | `EVOLUCAO`), `local_captura_id`, `capturado_em`.

**Treinador** — `id`, `laboratorio_id`, `nome`, `sprite`, `nivel`, `experiencia`, `status` (`DISPONIVEL` | `EM_EXPEDICAO` | `DESCANSANDO`), `expedicoes_concluidas`.

**Expedicao** — `id`, `laboratorio_id`, `treinador_id`, `local_destino_id`, `local_origem_id`, `status` (`EM_CURSO` | `CONCLUIDA_SUCESSO` | `CONCLUIDA_FALHA` | `ABORTADA`), `seed`, `started_at`, `eta`, `resolvida_em`, `duracao_minutos`, `dificuldade_calculada`, `poder_time_calculado`.

**ExpedicaoEvento** — `id`, `expedicao_id`, `ordem`, `tipo` (`PARTIDA` | `BATALHA` | `CAPTURA` | `CAPTURA_FALHA` | `DESCOBERTA` | `ITEM` | `CONTRATEMPO` | `SUBIU_NIVEL` | `EVOLUCAO` | `RETORNO`), `texto`, `payload` (JSONB), `ocorrido_em_minuto`.

**ExpedicaoItem** — `expedicao_id`, `item_id`, `quantidade_levada`, `quantidade_consumida`.

**ItemEstoque** — `laboratorio_id`, `item_id`, `quantidade`.

**LocalDesbloqueado** — `laboratorio_id`, `local_id`, `desbloqueado_em`.

**PokedexEntrada** — `laboratorio_id`, `especie_id`, `visto` (bool), `capturado` (bool), `primeiro_visto_em`.

### 3.3 Invariantes do domínio

1. Um treinador tem no máximo 3 Pokémon no time.
2. Um Pokémon pertence a no máximo um treinador por vez.
3. Um treinador em `EM_EXPEDICAO` não pode ter o time alterado nem ser enviado a outra expedição.
4. Pokémon alocados a um treinador em expedição não podem ser desatribuídos.
5. Um laboratório tem no máximo `slots_expedicao` (2) expedições com status `EM_CURSO`.
6. O destino de uma expedição deve ser vizinho de um local desbloqueado — ou o próprio laboratório, para a primeira.
7. Nenhum Pokémon ultrapassa o nível 100.
8. Uma expedição só é resolvida uma vez (idempotência garantida por lock + checagem de status).
9. O estoque de itens nunca fica negativo; a carga é debitada no envio, não no retorno.
10. Os starters são concedidos exatamente uma vez por laboratório.

---

## 4. Regras de jogo

Todas as constantes vivem em um arquivo de configuração (`app/game/balance.py`) e são tratadas como parâmetros de tuning, não como código. As fórmulas abaixo são o contrato; os números são o ponto de partida.

### 4.1 Experiência e nível

Ganho por batalha vencida, repartido entre os Pokémon do time:

```
exp_ganha = (experiencia_base_derrotado * nivel_derrotado / 7) / participantes
```

Experiência total para alcançar o nível `n`, por curva de crescimento:

```
rapida        = 0.8  * n^3
media_rapida  =        n^3
media_lenta   = 1.2  * n^3 - 15 * n^2 + 100 * n - 140
lenta         = 1.25 * n^3
```

A evolução dispara na resolução da expedição quando `nivel >= evolui_em_nivel` e a espécie tem `evolui_para_id`. Gera evento `EVOLUCAO` no relatório.

### 4.2 Poder do time e dificuldade do local

```
poder_pokemon = nivel * (1 + (soma_stats_base / 600)) * (hp_atual_pct / 100)
poder_time    = soma(poder_pokemon) * multiplicador_nivel_treinador
multiplicador_nivel_treinador = 1 + (nivel_treinador * 0.03)

dificuldade = nivel_selvagem_medio * nivel_dificuldade_local * FATOR_DIFICULDADE
razao       = poder_time / dificuldade
```

Probabilidade de vencer um encontro, achatada em sigmoide para evitar vitória ou derrota garantidas:

```
p_vitoria = clamp(1 / (1 + e^(-2.5 * (razao - 1))), 0.05, 0.95)
```

**Conforme a ideia original, a dificuldade da expedição é função do nível dos Pokémon que o treinador recebeu** — ela aparece no `razao` acima, e é o que o professor manipula ao montar o time.

### 4.3 Duração da expedição

A duração é a soma de dois tempos com significados diferentes: **atravessar** o caminho até o destino, e **explorar** o destino.

```
caminho          = menor rota de locais entre a origem e o destino
tempo_viagem     = soma de custo_travessia_minutos de cada local do caminho, exceto a origem
tempo_exploracao = encontros_base_destino * MINUTOS_POR_ENCONTRO

duracao = (tempo_viagem + tempo_exploracao)
        * (1 - min(nivel_treinador * 0.02, 0.40))     # treinador experiente é mais rápido
        * (1 - bonus_itens)                            # carga de suporte acelera
        / EXPEDITION_TIME_SCALE
```

`bonus_itens` é limitado a 0.25. Custo de travessia por tipo: cidade 3 min, rota 4 min, masmorra 8 min.

Esta formulação tem três consequências deliberadas. **Desbloquear um local encurta de verdade** as expedições que partem dele — uma ida a Mt. Moon partindo de Pallet leva 55 minutos, partindo de Route 3 leva 29. Sem isso, o desbloqueio só destravaria destinos, e o SDD prometia mais que isso. **Nenhum local tem duração arbitrária**: ela emerge do caminho, e corrigir o mapa corrige os tempos. E **o rendimento deixa de ser refém do relógio** — ver 4.4.

### 4.4 Encontros

```
qtd_encontros = max(1, encontros_base_destino + aleatorio(-1, +1))
```

A quantidade de encontros vem de `encontros_base` do destino, declarado no seed, e **não** é derivada da duração. Ritmo da sessão e rendimento da expedição são decisões de design separadas: Pallet Town rende 2 encontros porque é o quintal de casa, não porque fica perto.

Valores atuais: de 2 (Pallet Town) a 7 (Mt. Moon). A tabela completa, com os pesos de cada espécie, está em [docs/encontros.md](docs/encontros.md), gerada de `data/seed/` por `tools/tabela_encontros.py`.

Para cada encontro, sorteia-se a espécie pelo `peso` da tabela `LocalEncontro` e o nível na faixa do local. Rola-se `p_vitoria`:

- **Vitória:** evento `BATALHA`, distribui EXP, possível `SUBIU_NIVEL` e `EVOLUCAO`, reduz `hp_atual_pct` do time em 3 a 8 pontos.
- **Derrota:** evento `CONTRATEMPO`, consome uma Poção ou um Revive se houver, reduz `hp_atual_pct` em 15 a 30. Três derrotas sem itens de cura **encerram a expedição em falha** e o treinador volta mais cedo e sem capturas.

### 4.5 Captura

Só há tentativa de captura após vitória, e só se restar Pokébola na carga e slot de captura.

```
slots_captura = min(pokebolas_na_carga, 1 + nivel_treinador // 5)

p_captura = clamp(
    (taxa_captura / 255)
  * multiplicador_bola
  * (1 + (nivel_time_medio - nivel_selvagem) * 0.02)
  * FATOR_CAPTURA,
  0.05, 0.90)
```

Multiplicadores: Pokébola 1.0, Great Ball 1.5, Ultra Ball 2.0. Sucesso gera `CAPTURA`, consome a bola, cria a `PokemonInstancia` no laboratório ao fim da expedição e marca a Pokédex. Falha gera `CAPTURA_FALHA` e consome a bola.

**O número de Pokémon capturáveis por expedição é limitado por `slots_captura`**, exatamente como pedido: nível do treinador mais Pokébolas na mochila.

### 4.6 Descoberta e desbloqueio

Uma espécie vista pela primeira vez gera `DESCOBERTA` e marca `visto` na Pokédex mesmo sem captura.

Uma expedição `CONCLUIDA_SUCESSO` grava `LocalDesbloqueado` para o destino. A partir daí, novas expedições podem partir desse local, e seus vizinhos tornam-se destinos válidos. O laboratório (Pallet) é o único local desbloqueado na criação do perfil.

### 4.7 Pós-expedição

O treinador entra em `DESCANSANDO` por um período proporcional ao desgaste e depois volta a `DISPONIVEL`. Pokémon retornam com o `hp_atual_pct` reduzido, recuperado passivamente ao longo do tempo enquanto estiverem no laboratório.

---

## 5. Arquitetura técnica

### 5.1 Estrutura do repositório

```
PokeLab/
├── SDD.md                      # este documento
├── docker-compose.yml          # postgres + api + web
├── .env.example
├── .github/workflows/ci.yml    # invoca ci/pipeline.sh
├── ci/pipeline.sh              # lint -> test -> build (fonte da verdade)
├── specs/                      # artefatos SDD por feature
│   ├── constitution.md         # princípios invioláveis do projeto
│   └── NNN-nome-da-feature/
│       ├── spec.md             # o quê e por quê (sem solução técnica)
│       ├── plan.md             # como (arquitetura, contratos, modelo)
│       └── tasks.md            # lista ordenada e verificável
├── data/
│   ├── seed/                   # JSON normalizado versionado
│   └── sprites/                # PNGs dos 151
├── tools/
│   ├── ingest_pokeapi.py       # ETL -> data/seed
│   └── simulate_balance.py     # Monte Carlo de expedições
├── api/
│   ├── pyproject.toml          # ruff + pytest
│   ├── alembic/
│   └── app/
│       ├── main.py
│       ├── core/               # config, segurança, sessão de banco
│       ├── models/             # SQLAlchemy
│       ├── schemas/            # Pydantic (contrato da API)
│       ├── repositories/
│       ├── services/           # casos de uso
│       ├── seed.py             # carga idempotente de data/seed no banco
│       ├── game/               # DOMÍNIO PURO, sem I/O
│       │   ├── balance.py      # todas as constantes de tuning
│       │   ├── experience.py
│       │   ├── power.py
│       │   ├── capture.py
│       │   ├── encounter.py    # interface EncounterResolver
│       │   └── expedition.py   # orquestra a resolução
│       └── routers/
└── web/
    ├── package.json            # eslint + vitest
    └── src/
        ├── api/                # cliente gerado do OpenAPI
        ├── pages/              # Login, Laboratorio, Treinadores, Mapa, Expedicoes, Pokedex
        ├── components/
        └── store/
```

### 5.2 Princípio central

`api/app/game/` é **Python puro, determinístico, sem acesso a banco, rede ou relógio**. Recebe estado e um PRNG semeado, devolve resultado e lista de eventos. É onde vivem todas as fórmulas da seção 4, e é testável sem subir infraestrutura. Tudo o que for I/O fica em `services/` e `repositories/`.

Essa fronteira é o que permite o ADR-003 (trocar a resolução probabilística por uma engine de turnos) sem reescrever o jogo.

### 5.3 Contrato da API (superfície da v1)

```
POST   /auth/login                      -> token de sessão
POST   /auth/register                   -> cria professor + laboratório + starters
GET    /me                              -> professor + laboratório

GET    /pokemon                         -> lista do laboratório (filtros, paginação)
GET    /pokemon/{id}
PATCH  /pokemon/{id}                    -> apelido

GET    /trainers
POST   /trainers                        -> recruta NPC
GET    /trainers/{id}
PUT    /trainers/{id}/team              -> define time (0..3 ids)

GET    /map                             -> grafo com locais desbloqueados e destinos válidos
GET    /map/{local_id}                  -> detalhe, pool de encontros conhecido

GET    /expeditions                     -> ativas e histórico
POST   /expeditions                     -> {trainer_id, local_id, carga[]}
GET    /expeditions/{id}                -> resolve preguiçosamente se eta vencido
POST   /expeditions/{id}/claim          -> aplica recompensas, muda status
DELETE /expeditions/{id}                -> aborta (sem recompensa)

GET    /items                           -> estoque
GET    /pokedex                         -> 151 com visto/capturado
```

### 5.4 Infraestrutura

`docker compose` com três serviços: `db` (Postgres 16), `api` (uvicorn), `web` (build estático servido por nginx). Variáveis de ambiente sempre em `env_file` separado, nunca inline em `environment:`, conforme o padrão já estabelecido. Pipeline: job `lint` (ruff no `api/`, ESLint no `web/`) antes de `test`, antes de `build`.

---

## 6. Fases do projeto

Dez fases. Cada uma tem um entregável demonstrável e um critério de pronto objetivo. Fases com o mesmo número de ordem podem correr em paralelo.

---

### Fase 0 — Fundação do Laboratório — CONCLUÍDA (2026-11-05)
*Scaffold, infraestrutura local e o ritual SDD.*

| # | Tarefa | Agente | Skills |
|---|---|---|---|
| 0.1 | Criar `specs/constitution.md` com os princípios invioláveis (domínio puro, servidor autoritativo, seed versionado, aleatoriedade semeada) | `pokelab-architect` | `pokelab-spec` |
| 0.2 | Esqueleto do repositório conforme 5.1, com `.gitignore` e `.env.example` | `pokelab-infra` | — |
| 0.3 | `api/` com FastAPI, `pyproject.toml`, ruff, pytest, healthcheck | `pokelab-api` | `pokelab-api-conventions` |
| 0.4 | `web/` com Vite + React + TS, ESLint, Vitest, roteamento base | `pokelab-frontend` | `pokelab-ui-kit` |
| 0.5 | `docker-compose.yml` (db + api + web) com `env_file` separado | `pokelab-infra` | — |
| 0.6 | Alembic configurado, migração inicial vazia | `pokelab-api` | — |
| 0.7 | Pipeline CI: lint → test → build | `pokelab-infra` | — |
| 0.8 | `.claude/agents/` e `.claude/skills/` do projeto (seção 7) | `pokelab-architect` | `skill-creator` |

**Pronto quando:** `docker compose up` sobe os três serviços, `/health` responde, a SPA carrega, e o CI passa num commit vazio.

---

### Fase 1 — Pokédex Nacional — CONCLUÍDA (2026-11-05)
*Ingestão dos dados e sprites dos 151, e do mapa de Kanto.*

Spec em [specs/001-seed-de-dados/](specs/001-seed-de-dados/). Resultado: 151 espécies, 302 sprites (3,6 MB), 10 locais, 40 entradas de encontro, 6 itens. 40 testes verdes.

| # | Tarefa | Agente | Skills |
|---|---|---|---|
| 1.1 | `tools/ingest_pokeapi.py`: baixa espécies 1–151, normaliza para o schema de 3.1, grava `data/seed/species.json` | `pokelab-data` | `pokelab-data-seed` |
| 1.2 | Baixar e otimizar sprites (frente/costas) para `data/sprites/` | `pokelab-data` | `pokelab-data-seed` |
| 1.3 | Curvas de evolução dos 151 (gatilho por nível apenas) — 51 das 151 espécies evoluem por nível; pedra, troca e amizade ficam fora da v1 (questão 17) | `pokelab-data` | `pokelab-data-seed` |
| 1.4 | `data/seed/locations.json`: grafo do recorte v1 (10 locais, abaixo), com dificuldade, faixa de nível e duração base | `pokelab-architect` | `pokelab-domain-rules` |
| 1.5 | `data/seed/encounters.json`: pool de encontros por local com pesos | `pokelab-data` | `pokelab-domain-rules` |
| 1.6 | `data/seed/items.json`: Pokébola, Great Ball, Ultra Ball, Poção, Super Poção, Revive | `pokelab-data` | — |
| 1.7 | Migrações e comando `seed` que carrega os JSONs no Postgres de forma idempotente | `pokelab-api` | — |
| 1.8 | Testes de integridade do seed: 151 espécies, todo local alcançável a partir de Pallet, todo pool não vazio | `pokelab-test` | — |

**Recorte do mapa na v1** (decidido em 2026-11-05):

```
Pallet Town (lab, inicial)
  └─ Route 1 ─ Viridian City ─┬─ Route 22 (ramo sem saída, dificuldade alta)
                              └─ Route 2 ─ Viridian Forest ─ Pewter City
                                             └─ Route 3 ─ Mt. Moon ─ Cerulean City
```

Dez nós, uma ramificação precoce (Route 22 como armadilha de dificuldade) e profundidade suficiente para o desbloqueio significar algo. O restante de Kanto entra numa versão posterior apenas somando linhas no seed, sem mudança de código.

**Pronto quando:** `make seed` popula o banco do zero e os testes de integridade passam.

---

### Fase 2 — Credenciais do Professor
*Login, sessão e criação do laboratório.*

| # | Tarefa | Agente | Skills |
|---|---|---|---|
| 2.1 | Modelo `Professor` e `Laboratorio`, migração | `pokelab-api` | — |
| 2.2 | `POST /auth/register` e `POST /auth/login` com hash de senha e token de sessão (JWT simples, expiração curta) | `pokelab-api` | `pokelab-api-conventions` |
| 2.3 | Dependência de autenticação e escopo por laboratório em todas as rotas | `pokelab-api` | `pokelab-api-conventions` |
| 2.4 | Concessão dos 3 starters no registro (Bulbasaur, Charmander, Squirtle, nível 5) | `pokelab-domain` | `pokelab-domain-rules` |
| 2.5 | Desbloqueio inicial de Pallet | `pokelab-domain` | `pokelab-domain-rules` |
| 2.6 | Telas de Login e Registro; guarda de rota; persistência do token | `pokelab-frontend` | `pokelab-ui-kit` |
| 2.7 | **Kit inicial**: 1 treinador concedido, estoque inicial de Pokébolas e Poções, definidos em `balance.py` | `pokelab-domain` | `pokelab-domain-rules` |
| 2.8 | Testes: registro concede exatamente 3 starters, 1 treinador e o kit, uma única vez; rota protegida rejeita sem token | `pokelab-test` | — |

**Pronto quando:** registrar leva ao laboratório com 3 starters, 1 treinador e Pokébolas suficientes para a primeira expedição; recarregar a página mantém a sessão.

---

### Fase 3 — O Laboratório
*Tela principal, acervo de Pokémon e Pokédex.*

| # | Tarefa | Agente | Skills |
|---|---|---|---|
| 3.1 | `GET /pokemon` com filtro por tipo, nível, atribuição, e paginação | `pokelab-api` | `pokelab-api-conventions` |
| 3.2 | `GET /pokemon/{id}` com stats calculados por nível | `pokelab-api` | — |
| 3.3 | `PATCH /pokemon/{id}` (apelido) | `pokelab-api` | — |
| 3.4 | Servir sprites como estáticos com cache longo | `pokelab-infra` | — |
| 3.5 | Tela Laboratório: cabeçalho com recursos, lista de Pokémon, estado vazio | `pokelab-frontend` | `pokelab-ui-kit` |
| 3.6 | Painel de detalhe do Pokémon (sprite, tipos, stats, EXP até o próximo nível, origem) | `pokelab-frontend` | `pokelab-ui-kit` |
| 3.7 | `GET /pokedex` e tela da Pokédex (151 slots, silhueta para não visto) | `pokelab-api` + `pokelab-frontend` | `pokelab-ui-kit` |
| 3.8 | `GET /items` e painel de mochila | `pokelab-api` + `pokelab-frontend` | — |

**Pronto quando:** o professor vê, filtra e inspeciona seus Pokémon e sua Pokédex sem recarregar a página.

---

### Fase 4 — Corpo de Treinadores
*NPCs e montagem de times.*

| # | Tarefa | Agente | Skills |
|---|---|---|---|
| 4.1 | Modelo `Treinador`, migração, gerador de nome e avatar (ver questão 16) | `pokelab-domain` | `pokelab-domain-rules` |
| 4.2 | `POST /trainers` — recrutamento (custo e limite definidos em `balance.py`) | `pokelab-api` | — |
| 4.3 | `PUT /trainers/{id}/team` com validação dos invariantes 1–4 da seção 3.3 | `pokelab-domain` + `pokelab-api` | `pokelab-domain-rules` |
| 4.4 | Nível e EXP do treinador: ganho por expedição concluída (contrato definido aqui, aplicado na Fase 7) | `pokelab-domain` | `pokelab-domain-rules` |
| 4.5 | Tela Treinadores: lista com status, cartão por treinador | `pokelab-frontend` | `pokelab-ui-kit` |
| 4.6 | Montagem de time por seleção em lista (sem drag-and-drop), com prévia de poder do time | `pokelab-frontend` | `pokelab-ui-kit` |
| 4.7 | Testes dos invariantes: 4º Pokémon rejeitado, Pokémon em dois times rejeitado, time travado em expedição | `pokelab-test` | — |

**Pronto quando:** é possível recrutar um treinador, montar um time de 3 e ver o poder resultante.

---

### Fase 5 — Mapa de Kanto
*Grafo de locais, progressão e desbloqueio.*

| # | Tarefa | Agente | Skills |
|---|---|---|---|
| 5.1 | Modelos `Local`, `LocalEncontro`, `LocalDesbloqueado` | `pokelab-api` | — |
| 5.2 | `GET /map`: locais desbloqueados, destinos válidos e bloqueados com o motivo | `pokelab-domain` + `pokelab-api` | `pokelab-domain-rules` |
| 5.3 | Regra de adjacência (invariante 6) e cálculo do local de origem da expedição | `pokelab-domain` | `pokelab-domain-rules` |
| 5.4 | `GET /map/{id}`: dificuldade, faixa de nível, duração estimada, espécies já vistas ali | `pokelab-api` | — |
| 5.5 | Tela Mapa: lista hierárquica por região com estado por local (desbloqueado / disponível / bloqueado) | `pokelab-frontend` | `pokelab-ui-kit` |
| 5.6 | Testes: destino não adjacente rejeitado; desbloqueio expande o conjunto de destinos | `pokelab-test` | — |

**Pronto quando:** o mapa mostra corretamente o que está aberto, o que é alcançável e o que falta para abrir o resto.

---

### Fase 6 — Despacho de Expedições
*Envio, carga, slots e contagem de tempo.*

| # | Tarefa | Agente | Skills |
|---|---|---|---|
| 6.1 | Modelos `Expedicao`, `ExpedicaoItem`, `ExpedicaoEvento` | `pokelab-api` | — |
| 6.2 | `game/expedition.py`: cálculo de duração (4.3), dificuldade e poder do time (4.2) | `pokelab-domain` | `pokelab-domain-rules` |
| 6.3 | `POST /expeditions`: valida invariantes 3, 5, 6 e 9, debita carga, grava `seed`, `started_at` e `eta` | `pokelab-api` | `pokelab-api-conventions` |
| 6.4 | `GET /expeditions` com tempo restante calculado no servidor | `pokelab-api` | — |
| 6.5 | `DELETE /expeditions/{id}`: aborto sem recompensa, itens não devolvidos | `pokelab-api` | — |
| 6.6 | `EXPEDITION_TIME_SCALE` via configuração (ADR-004) | `pokelab-infra` | — |
| 6.7 | Tela de despacho: escolher treinador, destino, carga; prévia de duração, dificuldade e chance estimada | `pokelab-frontend` | `pokelab-ui-kit` |
| 6.8 | Painel de expedições ativas com contador regressivo e polling leve | `pokelab-frontend` | `pokelab-ui-kit` |
| 6.9 | Testes: 3ª expedição simultânea rejeitada; treinador ocupado rejeitado; estoque debitado corretamente | `pokelab-test` | — |

**Pronto quando:** duas expedições correm simultaneamente, com contador regressivo correto após recarregar a página.

---

### Fase 7 — Relatório de Campo
*O motor. Resolução de encontros, EXP, captura, evolução e retorno.*

Esta é a fase de maior risco técnico e a que define o jogo. Nenhuma tarefa aqui toca I/O além da camada de serviço.

| # | Tarefa | Agente | Skills |
|---|---|---|---|
| 7.1 | `game/experience.py`: ganho de EXP e curvas de crescimento (4.1), com testes de tabela | `pokelab-domain` | `pokelab-domain-rules` |
| 7.2 | `game/power.py`: poder do Pokémon, do time e dificuldade (4.2) | `pokelab-domain` | `pokelab-domain-rules` |
| 7.3 | `game/capture.py`: probabilidade e slots de captura (4.5) | `pokelab-domain` | `pokelab-domain-rules` |
| 7.4 | `game/encounter.py`: interface `EncounterResolver` e implementação probabilística (ADR-003) | `pokelab-domain` | `pokelab-domain-rules` |
| 7.5 | `game/expedition.py::resolve()`: loop de encontros, consumo de itens, desgaste, falha por 3 derrotas, geração ordenada de eventos | `pokelab-domain` | `pokelab-domain-rules` |
| 7.6 | Textos narrativos dos eventos em português, por tipo, com interpolação de nomes e números | `pokelab-domain` | `pokelab-ui-kit` |
| 7.7 | Resolução preguiçosa idempotente no `GET /expeditions/{id}`: transação com `SELECT ... FOR UPDATE` e checagem de status | `pokelab-api` | `pokelab-api-conventions` |
| 7.8 | `POST /expeditions/{id}/claim`: cria Pokémon capturados, aplica EXP e evoluções, marca Pokédex, desbloqueia o local, libera o treinador | `pokelab-api` | `pokelab-domain-rules` |
| 7.9 | Tela de relatório de campo: timeline de eventos, resumo de capturas, EXP e itens consumidos | `pokelab-frontend` | `pokelab-ui-kit` |
| 7.10 | Testes determinísticos por seed: mesma entrada produz exatamente o mesmo relatório | `pokelab-test` | — |
| 7.11 | **Recompensa de itens**: evento `ITEM` na resolução, repondo Pokébolas e curas conforme a dificuldade do local | `pokelab-domain` | `pokelab-domain-rules` |
| 7.12 | Testes de idempotência: duas chamadas concorrentes resolvem uma única vez | `pokelab-test` | — |

**Pronto quando:** uma expedição enviada retorna com relatório coerente, os Pokémon ganham nível, pelo menos um é capturado e o local é desbloqueado.

---

### Fase 8 — Calibragem
*Transformar números arbitrários em curva de progressão defensável.*

| # | Tarefa | Agente | Skills |
|---|---|---|---|
| 8.1 | `tools/simulate_balance.py`: Monte Carlo de N expedições variando nível de time, treinador e local | `pokelab-balance` | `pokelab-domain-rules` |
| 8.2 | Relatório de curvas: taxa de sucesso, capturas por hora, EXP por hora, tempo até desbloquear Kanto inteiro | `pokelab-balance` | `dataviz` |
| 8.3 | Ajustar `balance.py` para as metas: ~70% de sucesso com time adequado, ~25% com time subnivelado | `pokelab-balance` | `pokelab-domain-rules` |
| 8.6 | Calibrar `custo_travessia_minutos` e `encontros_base` por local: duração percebida, rendimento por hora e o ganho real de desbloquear cada local | `pokelab-balance` | `pokelab-data-seed` |
| 8.4 | Testes de regressão de balanceamento (faixas aceitáveis, não valores exatos) | `pokelab-test` | — |
| 8.5 | Calibrar a economia de itens (tarefa 7.11) para que o estoque não seque nem acumule | `pokelab-balance` | `pokelab-domain-rules` |

**Pronto quando:** a simulação mostra progressão sem travas nem trivialidade, e as faixas estão fixadas em teste.

---

### Fase 9 — Acabamento
*Tornar jogável de verdade.*

| # | Tarefa | Agente | Skills |
|---|---|---|---|
| 9.1 | Estados de carregamento, erro e vazio em todas as telas | `pokelab-frontend` | `pokelab-ui-kit` |
| 9.2 | Notificação no app quando uma expedição retorna | `pokelab-frontend` | `pokelab-ui-kit` |
| 9.3 | Responsividade mínima e tema claro/escuro | `pokelab-frontend` | `pokelab-ui-kit` |
| 9.4 | Tratamento uniforme de erro da API (código, mensagem em português, correlação) | `pokelab-api` | `pokelab-api-conventions` |
| 9.5 | Teste de ponta a ponta do loop completo: registrar → montar time → expedir → relatório → desbloquear | `pokelab-test` | — |
| 9.6 | Revisão de segurança: escopo por laboratório em toda rota, sem IDOR | `pokelab-test` | `security-review` |
| 9.7 | **Revisão de escopo de evolução** (questão 17): decidir o destino das 100 espécies que não evoluem por nível — pedra, troca e amizade. Levantar quantas estão afetadas por grupo, o custo de cada mecânica e o impacto na Pokédex, e registrar a decisão em ADR | `pokelab-architect` | `pokelab-domain-rules` |

**Pronto quando:** uma pessoa que nunca viu o projeto completa o loop sem instrução, e a decisão sobre evolução pós-v1 está registrada.

---

### Fase 10 — Implantação
*Colocar de pé no servidor.*

| # | Tarefa | Agente | Skills |
|---|---|---|---|
| 10.1 | Dockerfiles de produção (multi-stage) para `api` e `web` | `pokelab-infra` | — |
| 10.2 | Pipeline GitHub Actions no padrão estabelecido: lint → test → build → Artifact Registry via WIF → deploy SSH com `docker compose` | `pokelab-infra` | — |
| 10.3 | `docker-compose.yml` do servidor com `env_file` separado | `pokelab-infra` | — |
| 10.4 | Backup do Postgres e procedimento de restauração | `pokelab-infra` | `operations:runbook` |
| 10.5 | Logs estruturados e healthchecks nos serviços | `pokelab-infra` | — |
| 10.6 | Runbook de operação: deploy, rollback, reseed, inspeção de expedição travada | `pokelab-infra` | `operations:runbook` |

**Pronto quando:** `git push` na branch principal publica a versão e o runbook cobre rollback.

---

### Caminho crítico

```
Fase 0 ──> Fase 1 ──┬──> Fase 2 ──> Fase 3 ──┐
                    │                         ├──> Fase 6 ──> Fase 7 ──> Fase 8 ──> Fase 9 ──> Fase 10
                    └──> Fase 4 ──> Fase 5 ──┘
```

Fases 3, 4 e 5 podem correr em paralelo depois da Fase 2. A Fase 7 é o gargalo: nada depois dela faz sentido antes dela estar correta.

---

## 7. Agentes e skills

Artefatos a criar em `.claude/agents/` e `.claude/skills/` do repositório na tarefa 0.8.

### 7.1 Agentes

| Agente | Responsabilidade | Ferramentas | Modelo |
|---|---|---|---|
| `pokelab-architect` | Escreve e revisa specs, mantém constitution e ADRs, decompõe fases em tarefas. Não escreve código de aplicação. | Read, Write, Edit, Grep, Glob | opus |
| `pokelab-domain` | Implementa exclusivamente `api/app/game/`. Proibido de importar SQLAlchemy, FastAPI, `datetime.now` ou `random` sem seed. | Read, Write, Edit, Bash (pytest) | opus |
| `pokelab-api` | Rotas, schemas Pydantic, modelos SQLAlchemy, repositórios, migrações Alembic. Delega regra de jogo ao domínio. | Read, Write, Edit, Bash | sonnet |
| `pokelab-frontend` | `web/`: páginas, componentes, estado, cliente da API. | Read, Write, Edit, Bash | sonnet |
| `pokelab-data` | `tools/ingest_pokeapi.py` e o conteúdo de `data/seed/`. Único agente autorizado a acessar a rede. | Read, Write, Edit, Bash, WebFetch | sonnet |
| `pokelab-balance` | Simulações de Monte Carlo e ajuste de `balance.py`. Só pode alterar constantes, nunca fórmulas. | Read, Edit, Bash | opus |
| `pokelab-test` | Testes pytest e Vitest. Escreve teste que falha antes da correção; não altera código de produção para fazer teste passar. | Read, Write, Edit, Bash | sonnet |
| `pokelab-infra` | Docker, compose, CI/CD, runbooks. | Read, Write, Edit, Bash | sonnet |

### 7.2 Skills do projeto

| Skill | Conteúdo | Quando carrega |
|---|---|---|
| `pokelab-spec` | Formato de `spec.md`, `plan.md` e `tasks.md`; regra de que spec descreve comportamento observável e nunca implementação; critérios de pronto verificáveis. | Antes de abrir qualquer feature nova. |
| `pokelab-domain-rules` | Fonte única das fórmulas da seção 4, nomes canônicos das constantes, invariantes da seção 3.3, e o veto de I/O em `game/`. | Qualquer tarefa que toque regra de jogo ou balanceamento. |
| `pokelab-api-conventions` | Nomenclatura de rotas, envelope de erro, paginação, códigos HTTP, autenticação, regra de escopo por laboratório, padrão de migração. | Qualquer tarefa em `api/app/routers/` ou `schemas/`. |
| `pokelab-ui-kit` | Tokens de cor e espaçamento, componentes base (lista, cartão, botão, contador, timeline), regra de que a UI é lista-e-botão sem animação, vocabulário em português do jogo. | Qualquer tarefa em `web/`. |
| `pokelab-data-seed` | Como rodar o ingestor, formato dos JSONs, política de versionamento dos sprites, checagens de integridade obrigatórias. | Fase 1 e qualquer atualização de dados. |

### 7.3 Skills existentes aproveitadas

`skill-creator` (0.8), `dataviz` (8.2), `security-review` (9.6), `operations:runbook` (10.4, 10.6), `code-review` ao fechar cada fase.

---

## 8. O ciclo SDD

Para cada item de fase que não seja trivial:

1. **Especificar** — `specs/NNN-nome/spec.md`: o comportamento observável, as regras, os critérios de aceite. Sem tecnologia. Escrito por `pokelab-architect`.
2. **Planejar** — `plan.md`: contratos de API, mudanças de modelo, arquivos afetados, riscos. Só aqui entra decisão técnica.
3. **Decompor** — `tasks.md`: tarefas ordenadas, cada uma verificável isoladamente, com o agente responsável.
4. **Implementar** — o agente designado executa uma tarefa por vez.
5. **Verificar** — `pokelab-test` confere contra os critérios de aceite da `spec.md`, não contra o código.
6. **Revisar** — `code-review` antes de fechar a fase.

A spec é atualizada quando a realidade diverge dela. Código que contraria a spec é bug — da spec ou do código, e decidir qual é o primeiro passo da correção.

---

## 9. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| Fórmulas de balanceamento produzem progressão sem graça | Alto — mata o jogo | Fase 8 com simulação antes de qualquer ajuste manual; constantes isoladas de fórmulas |
| Resolução preguiçosa concorrente duplica recompensas | Alto — corrompe estado | Lock de linha + checagem de status; teste 7.11 obrigatório |
| Escopo da Fase 7 cresce para engine de turnos | Alto — atrasa indefinidamente | ADR-003 fecha a decisão; a interface `EncounterResolver` é a válvula de escape |
| Dados da PokeAPI mudam ou saem do ar | Médio | Seed versionado no repositório; runtime nunca depende da API |
| Grafo de Kanto montado à mão fica incoerente | Médio | Teste 1.8: alcançabilidade de todo local a partir de Pallet |
| Sprites inflam o repositório | Baixo | Apenas frente/costas, PNG otimizado, 151 espécies |

---

## 10. Questões em aberto

Pontos que não bloqueiam o início, mas precisam de decisão antes das fases indicadas.

**Antes da Fase 2**
1. ~~Registro aberto ou fechado.~~ **Resolvido 2026-11-05: aberto.**
2. ~~Laboratórios por conta.~~ **Resolvido 2026-11-05: um por conta na v1.** Quando outras regiões entrarem, cada uma ganha seu laboratório. O modelo já suporta: `Laboratorio` tem `professor_id`, então a relação é 1:N desde o início e passar de um para vários não exige migração — apenas remover a validação de unicidade.

**Antes da Fase 4**
3. Como se recruta um treinador? Gratuito e ilimitado, por custo em moeda do jogo, ou recompensa de expedição?
4. Treinador pode ser perdido ou demitido? Há consequência numa falha grave?
5. Nome e sprite dos treinadores: gerados aleatoriamente de uma lista, ou nomeados pelo professor?

**Antes da Fase 5**
6. ~~Recorte do mapa.~~ **Resolvido 2026-11-05: 10 locais, Pallet até Cerulean (Fase 1).**
7. Alguma expedição precisa de pré-requisito além de adjacência (por exemplo, nível mínimo do treinador)?

**Antes da Fase 7**
8. Pokémon pode ser derrotado permanentemente, ou só fica machucado? (Assumi: só machucado, `hp_atual_pct` baixo.)
9. Pokémon capturado vem com o nível que tinha em campo, ou normalizado?
10. Pokémon atribuído a um treinador evolui durante a expedição, ou só no laboratório?
11. Há limite de capacidade do laboratório? Um sistema de "PC do Bill" faz sentido, ou armazenamento infinito na v1?

**Antes da Fase 8**
12. Qual sessão alvo? Expedições de 5 a 30 minutos pressupõem que você volta algumas vezes por dia. Se a intenção for uma sessão longa única, as durações precisam encolher.
13. Existe moeda? Sem economia, itens só vêm de expedição; com economia, aparece uma loja e o escopo cresce.

**Transversal**
14. ~~Host do repositório.~~ **Resolvido 2026-11-05: GitHub pessoal.** Workflow em `.github/workflows/ci.yml`, chamando `ci/pipeline.sh`.
17. **Evolução fora da v1**: 100 das 151 espécies não evoluem por nível. Parte nunca evolui (Mew, Tauros), parte depende de pedra (Pikachu→Raichu, Eevee) ou troca (Kadabra, Machoke). Entram numa versão posterior junto com uma mecânica de itens de evolução, ou ficam de fora para sempre? **Adiado deliberadamente para a tarefa 9.7, após a v1 estar jogável.**

18. ~~Piso de encontros achata metade do mapa.~~ **Resolvido 2026-11-05: desacoplado.** `encontros_base` por local no seed, e a duração passou a ser calculada pelo caminho (seções 4.3 e 4.4). Os números de travessia e de encontros foram escolhidos por estimativa e ainda não por simulação — a calibragem é da Fase 8, tarefa 8.3.
16. **Avatar do treinador**: o ADR-002 cobre apenas sprites de Pokémon. Sugiro avatar gerado (iniciais sobre cor determinística pelo id do treinador) — zero asset, zero licença, e substituível depois sem migração.
15. Idioma da interface: português apenas, ou nomes de Pokémon e locais em inglês com o restante em português? (Assumi a segunda opção, que é o padrão da comunidade.)
