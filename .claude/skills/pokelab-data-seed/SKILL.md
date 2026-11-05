---
name: pokelab-data-seed
description: Como funciona o seed de dados do PokeLab — ingestao da PokeAPI, formato dos JSONs, politica de sprites e checagens de integridade obrigatorias. Use nas tarefas da Fase 1 e em qualquer atualizacao de data/seed ou data/sprites.
---

# Seed de dados do PokeLab

## A regra que manda

Artigo V da constituicao: a aplicacao em execucao **nunca** chama a PokeAPI nem qualquer servico externo. Os dados vem de `data/seed/`, versionado no repositorio.

Atualizar dados e rodar o ingestor e commitar o diff. E um ato deliberado, nunca efeito colateral de um deploy.

## Arquivos

```
data/seed/species.json      151 especies
data/seed/locations.json    10 locais da v1, com o grafo de vizinhanca
data/seed/encounters.json   pool por local, com pesos
data/seed/items.json        Poke Ball, Great Ball, Ultra Ball, Potion, Super Potion, Revive
data/sprites/{id}-front.png
data/sprites/{id}-back.png
```

Campos exatamente como a secao 3.1 do `SDD.md` define. Nao repasse o JSON cru da PokeAPI.

JSON com indentacao de 2 espacos e chaves ordenadas, para o diff ser legivel.

## Recorte do mapa na v1

```
Pallet Town (laboratorio, inicial)
  └─ Route 1 ─ Viridian City ─┬─ Route 22
                              └─ Route 2 ─ Viridian Forest ─ Pewter City
                                             └─ Route 3 ─ Mt. Moon ─ Cerulean City
```

Dez nos. Route 22 e um ramo sem saida com dificuldade alta — armadilha deliberada para o professor que despacha sem olhar o nivel. Expandir o mapa depois e somar linhas em `locations.json` e `encounters.json`, sem tocar em codigo.

## O ingestor

`tools/ingest_pokeapi.py` e idempotente: rodar duas vezes produz diff nenhum.

Cache local em `data/cache/`, ignorado pelo git, reaproveitado entre execucoes. Requisicoes sequenciais com pausa — a PokeAPI e um servico publico e gratuito.

Sprites: apenas frente e costas, PNG otimizado, nomeados pelo id. Nada de shiny, animado ou de outras geracoes na v1.

## Checagens obrigatorias antes de gravar

1. Exatamente 151 especies, ids 1 a 151 sem buraco.
2. Nenhum campo obrigatorio nulo.
3. Toda `evolui_para_id` aponta para um id existente dentro dos 151.
4. Todo local alcancavel a partir de Pallet Town pelo grafo de vizinhanca.
5. Todo local tem pool de encontros nao vazio.
6. Toda especie referenciada em `encounters.json` existe em `species.json`.
7. Todo sprite referenciado existe no disco.

Essas checagens sao teste automatizado, nao conferencia manual.

## Carga no banco

O comando `make seed` carrega os JSONs no Postgres de forma idempotente: re-executar atualiza os registros existentes sem duplicar e sem apagar estado de jogo.

Dados de seed sao **imutaveis em runtime**. Nenhum endpoint escreve em `PokemonEspecie`, `Local`, `LocalEncontro` ou `Item`.

## Se a fonte nao tem o dado

Nao invente. Registre a lacuna na secao 10 do SDD e pergunte ao professor.
