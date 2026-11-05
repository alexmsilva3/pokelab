# 001 — Plano

## Abordagem

Duas fontes, dois tratamentos diferentes.

**Dados de espécie vêm da PokeAPI**, baixados uma vez por `tools/ingest_pokeapi.py` e gravados como JSON normalizado em `data/seed/`. Os sprites vêm do repositório público PokeAPI/sprites. Tudo versionado no git (Artigo V). A aplicação em execução nunca toca a rede.

**Dados de mundo são escritos à mão.** Lugares, vizinhanças, dificuldades e pools de encontro não existem numa API em formato utilizável, e são decisões de game design, não fatos. Ficam em `locations.json`, `encounters.json` e `items.json`, mantidos manualmente.

O carregamento no banco é um comando `python -m app.seed` que lê os JSONs e faz upsert por chave natural. Upsert, e não truncate-insert, porque a partida do professor referencia essas linhas.

## Modelo de dados

Quatro tabelas de referência, todas imutáveis em runtime:

| Tabela | Chave | Observação |
|---|---|---|
| `pokemon_especies` | `id` inteiro 1..151 | id é o número da Pokédex, não surrogate |
| `locais` | `id` texto kebab-case | `pallet-town`, legível em log e URL |
| `local_encontros` | `(local_id, especie_id)` | peso relativo e faixa de nível |
| `itens` | `id` texto kebab-case | `poke-ball`, igual ao slug da PokeAPI |

Chave natural em vez de surrogate nas três últimas: o seed precisa ser idempotente entre máquinas, e um id auto-incremento diverge entre instalações.

Vizinhança de locais em coluna `vizinhos` do tipo `ARRAY(String)` no Postgres, não em tabela de junção. São dez locais com arestas fixas, lidos sempre inteiros; a tabela de junção custaria um join em toda consulta de mapa sem nenhum ganho.

## Formato dos JSONs

`species.json` — lista de objetos com os campos da seção 3.1 do SDD. Ordenado por id, indentação de 2, chaves ordenadas, para o diff ser legível.

`locations.json` — lista com `id`, `nome`, `tipo`, `nivel_dificuldade`, `nivel_selvagem_min/max`, `duracao_base_minutos`, `vizinhos`, `e_inicial`.

`encounters.json` — mapa de `local_id` para lista de `{especie_id, peso, nivel_min, nivel_max}`.

`items.json` — lista com `id`, `nome`, `categoria`, `potencia`, `efeito_duracao`.

## Ingestor

Stdlib apenas (`urllib.request`, `json`, `pathlib`) — o ingestor roda fora da aplicação e não deve arrastar dependência para dentro dela.

Cache em `data/cache/`, ignorado pelo git. Reexecução com cache quente não faz nenhuma requisição e produz diff vazio.

Três endpoints por espécie: `/pokemon/{id}` (tipos, stats, base_experience), `/pokemon-species/{id}` (capture_rate, growth_rate, evolution_chain) e a cadeia de evolução, que é compartilhada entre as espécies de uma mesma família e por isso cacheada por url.

Sprites de `raw.githubusercontent.com/PokeAPI/sprites`, frente e costas, salvos como `{id}-front.png` e `{id}-back.png`.

## Evolução

Da cadeia de evolução interessa apenas o gatilho `level-up` com `min_level` preenchido, e apenas quando o alvo está entre os 151. Eevee, Pikachu via pedra e as trocas ficam com `evolui_para_id` nulo — registrado como pendência conhecida, não como bug.

## Riscos

| Risco | Mitigação |
|---|---|
| PokeAPI fora do ar durante o desenvolvimento | cache local; arquivos gerados são commitados |
| Diferença de ordem de chaves entre execuções gera diff ruidoso | `sort_keys=True` e ordenação explícita das listas |
| Pool de encontro escrito à mão citando espécie inexistente | teste de integridade cruzando com `species.json` |
| Local escrito à mão ficando ilhado no grafo | teste de alcançabilidade por busca em largura desde Pallet |

## Fora deste plano

Carga incremental por espécie. Interface de administração do acervo. Validação de schema por Pydantic nos JSONs de seed — os testes de integridade cobrem o que importa com menos cerimônia.
