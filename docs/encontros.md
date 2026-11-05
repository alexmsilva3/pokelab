# Tabela de encontros

Gerado por `tools/tabela_encontros.py` a partir de `data/seed/`. Não edite à mão:
altere `encounters.json` ou `locations.json` e rode o script de novo.

O peso de cada espécie é a porcentagem de aparecer num encontro daquele local —
os pesos de um local somam 100 por convenção. Quantos encontros uma expedição gera
é `encontros_base` do destino, independente de quanto tempo a viagem leva.

## Resumo dos locais

| Local | Tipo | Dificuldade | Nível selvagem | Encontros | Travessia | Espécies |
|---|---|---|---|---|---|---|
| Pallet Town | Cidade | 1 | 2–4 | 2 | 3 min | 2 |
| Route 1 | Rota | 1 | 2–5 | 3 | 4 min | 2 |
| Route 2 | Rota | 2 | 3–6 | 4 | 4 min | 4 |
| Viridian City | Cidade | 2 | 3–6 | 3 | 3 min | 3 |
| Pewter City | Cidade | 3 | 5–9 | 3 | 3 min | 4 |
| Viridian Forest | Masmorra | 3 | 4–8 | 6 | 8 min | 6 |
| Route 3 | Rota | 4 | 6–10 | 5 | 4 min | 4 |
| Mt. Moon | Masmorra | 5 | 7–12 | 7 | 8 min | 5 |
| Route 22 | Rota | 5 | 6–10 | 4 | 4 min | 5 |
| Cerulean City | Cidade | 6 | 10–14 | 4 | 3 min | 5 |

## Pallet Town

Cidade, dificuldade 1, 2 encontros por expedição, travessia de 3 min.

| # | Pokémon | Tipo | Peso | Nível | Taxa de captura |
|---|---|---|---|---|---|
| 016 | Pidgey | normal / flying | **50%** | 2–4 | 255 |
| 019 | Rattata | normal | **50%** | 2–4 | 255 |

## Route 1

Rota, dificuldade 1, 3 encontros por expedição, travessia de 4 min.

| # | Pokémon | Tipo | Peso | Nível | Taxa de captura |
|---|---|---|---|---|---|
| 016 | Pidgey | normal / flying | **55%** | 2–5 | 255 |
| 019 | Rattata | normal | **45%** | 2–5 | 255 |

## Route 2

Rota, dificuldade 2, 4 encontros por expedição, travessia de 4 min.

| # | Pokémon | Tipo | Peso | Nível | Taxa de captura |
|---|---|---|---|---|---|
| 016 | Pidgey | normal / flying | **30%** | 3–6 | 255 |
| 010 | Caterpie | bug | **25%** | 3–5 | 255 |
| 019 | Rattata | normal | **25%** | 3–5 | 255 |
| 013 | Weedle | bug / poison | **20%** | 3–5 | 255 |

## Viridian City

Cidade, dificuldade 2, 3 encontros por expedição, travessia de 3 min.

| # | Pokémon | Tipo | Peso | Nível | Taxa de captura |
|---|---|---|---|---|---|
| 019 | Rattata | normal | **40%** | 3–6 | 255 |
| 021 | Spearow | normal / flying | **35%** | 3–6 | 255 |
| 016 | Pidgey | normal / flying | **25%** | 3–6 | 255 |

## Pewter City

Cidade, dificuldade 3, 3 encontros por expedição, travessia de 3 min.

| # | Pokémon | Tipo | Peso | Nível | Taxa de captura |
|---|---|---|---|---|---|
| 019 | Rattata | normal | **30%** | 5–8 | 255 |
| 021 | Spearow | normal / flying | **30%** | 5–9 | 255 |
| 027 | Sandshrew | ground | **25%** | 6–9 | 255 |
| 074 | Geodude | rock / ground | **15%** | 6–9 | 255 |

## Viridian Forest

Masmorra, dificuldade 3, 6 encontros por expedição, travessia de 8 min.

| # | Pokémon | Tipo | Peso | Nível | Taxa de captura |
|---|---|---|---|---|---|
| 010 | Caterpie | bug | **28%** | 4–6 | 255 |
| 013 | Weedle | bug / poison | **28%** | 4–6 | 255 |
| 011 | Metapod | bug | **16%** | 5–8 | 120 |
| 014 | Kakuna | bug / poison | **16%** | 5–8 | 120 |
| 016 | Pidgey | normal / flying | **9%** | 4–7 | 255 |
| 025 | Pikachu | electric | **3%** | 5–8 | 190 |

Espécies raras deste local:

- **Pidgey**: 43% de aparecer por expedição, cerca de 2 expedições até a primeira vez.
- **Pikachu**: 17% de aparecer por expedição, cerca de 6 expedições até a primeira vez.

## Route 3

Rota, dificuldade 4, 5 encontros por expedição, travessia de 4 min.

| # | Pokémon | Tipo | Peso | Nível | Taxa de captura |
|---|---|---|---|---|---|
| 021 | Spearow | normal / flying | **30%** | 6–10 | 255 |
| 039 | Jigglypuff | normal / fairy | **25%** | 6–9 | 170 |
| 056 | Mankey | fighting | **25%** | 7–10 | 190 |
| 016 | Pidgey | normal / flying | **20%** | 6–9 | 255 |

## Mt. Moon

Masmorra, dificuldade 5, 7 encontros por expedição, travessia de 8 min.

| # | Pokémon | Tipo | Peso | Nível | Taxa de captura |
|---|---|---|---|---|---|
| 041 | Zubat | poison / flying | **35%** | 7–11 | 255 |
| 074 | Geodude | rock / ground | **25%** | 7–11 | 255 |
| 046 | Paras | bug / grass | **20%** | 7–10 | 190 |
| 027 | Sandshrew | ground | **12%** | 8–11 | 255 |
| 035 | Clefairy | fairy | **8%** | 9–12 | 150 |

Espécies raras deste local:

- **Clefairy**: 44% de aparecer por expedição, cerca de 2 expedições até a primeira vez.

## Route 22

Rota, dificuldade 5, 4 encontros por expedição, travessia de 4 min.

| # | Pokémon | Tipo | Peso | Nível | Taxa de captura |
|---|---|---|---|---|---|
| 021 | Spearow | normal / flying | **30%** | 6–9 | 255 |
| 056 | Mankey | fighting | **25%** | 6–10 | 190 |
| 029 | Nidoran♀ | poison | **20%** | 6–9 | 235 |
| 032 | Nidoran♂ | poison | **20%** | 6–9 | 235 |
| 019 | Rattata | normal | **5%** | 6–8 | 255 |

Espécies raras deste local:

- **Rattata**: 19% de aparecer por expedição, cerca de 5 expedições até a primeira vez.

## Cerulean City

Cidade, dificuldade 6, 4 encontros por expedição, travessia de 3 min.

| # | Pokémon | Tipo | Peso | Nível | Taxa de captura |
|---|---|---|---|---|---|
| 054 | Psyduck | water | **25%** | 10–14 | 190 |
| 060 | Poliwag | water | **25%** | 10–13 | 255 |
| 019 | Rattata | normal | **20%** | 10–12 | 255 |
| 098 | Krabby | water | **20%** | 11–14 | 225 |
| 120 | Staryu | water | **10%** | 12–14 | 225 |

Espécies raras deste local:

- **Staryu**: 34% de aparecer por expedição, cerca de 3 expedições até a primeira vez.
