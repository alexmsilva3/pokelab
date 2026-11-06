# 005 — Plano

## Abordagem

Fase de leitura pura: nenhuma escrita, nenhuma mudança de regra. O trabalho é um algoritmo de grafo no domínio e dois endpoints que o expõem.

O algoritmo não é busca em largura. Os custos de travessia diferem por tipo de local — cidade 3, rota 4, masmorra 8 —, então o caminho com menos arestas não é necessariamente o mais rápido. É **Dijkstra**, com os locais visitados como origens múltiplas.

Tratar isso como BFS seria um erro silencioso: hoje, no mapa linear de dez nós, as duas buscas concordam quase sempre, e um teste descuidado passaria. Quando o mapa crescer e houver caminho alternativo entre uma masmorra e duas rotas, a resposta divergiria sem ninguém notar.

## Domínio

`game/mapa.py`, puro, recebendo o grafo e o conjunto de visitados como dados:

```
alcancaveis(grafo, visitados)        -> vizinhos de visitados, menos os visitados
estado_de(local, visitados, alcanca) -> VISITADO | ALCANCAVEL | FORA_DE_ALCANCE
rotas_otimas(grafo, visitados)       -> por destino: origem, caminho, custo de travessia
proximo_passo(grafo, visitados, id)  -> o que visitar primeiro para abrir um bloqueado
duracao_estimada(custo_viagem, encontros_base, nivel_treinador, bonus_itens, escala)
```

`rotas_otimas` roda um Dijkstra multi-origem **uma vez** e devolve o mapa inteiro. Rodar por destino seria dez buscas para montar uma tela.

`duracao_estimada` já é a fórmula da seção 4.4 do SDD, extraída aqui porque a Fase 6 vai precisar dela igual. A Fase 6 depois só a chama com o treinador e a carga reais.

`proximo_passo` é o que responde "o que falta". Para um local fora de alcance, é o primeiro nó do caminho mais curto a partir dos visitados — a resposta útil é "visite Route 1", não "visite Route 1, depois Viridian, depois Route 2".

## Modelo

Uma tabela nova, `pokedex_avistamentos`, com chave composta `(laboratorio_id, especie_id, local_id)`, `primeiro_visto_em` e `vezes_visto`.

A Fase 5 **só lê**; quem escreve é a tarefa 7.10, na descarga da Pokédex. Criar agora tem dois motivos: a tela precisa consultar algo, e a migração sai de graça junto das outras em vez de virar uma migração isolada na Fase 7.

## Contratos de API

```
GET /map
    200 -> {items: [LocalNoMapa], visitados, total}

LocalNoMapa:
    id, nome, tipo, nivel_dificuldade, nivel_selvagem_min, nivel_selvagem_max
    estado: VISITADO | ALCANCAVEL | FORA_DE_ALCANCE
    origem_id, origem_nome, duracao_estimada_minutos   (nulos se fora de alcance)
    proximo_passo_id, proximo_passo_nome               (nulos se alcançável)

GET /map/{id}?treinador_id=
    200 -> LocalDetalhado   (o acima mais encontros_base e especies_avistadas)
    404 -> local inexistente

especies_avistadas: [{especie_id, nome, sprite, vezes_visto, primeiro_visto_em}]
```

`treinador_id` é opcional: sem ele a duração é a base, sem o desconto de nível. Com ele, a estimativa é a que aquele treinador teria de fato — que é a pergunta real do professor na hora de escolher quem mandar.

### O que a resposta não pode conter

A tabela `local_encontros` do seed **nunca** vai para o cliente. O professor vê apenas o que seus treinadores avistaram, de `pokedex_avistamentos`.

Isso vale também para contagens: devolver "3 de 6 espécies descobertas aqui" revela que existem seis, e permite ao professor saber que ainda falta caçar mesmo sem ter ido. Mesmo princípio da Pokédex na Fase 3, onde uma espécie desconhecida não tem sequer o campo nome.

`encontros_base` pode ir: é quantos encontros a expedição gera, não quais.

## Frontend

```
pages/Mapa.tsx                  lista ordenada por distância
components/CartaoLocal.tsx      estado, duração, origem, o que falta
components/EspeciesAvistadas.tsx
api/mapa.ts
```

Lista ordenada por custo de viagem a partir dos visitados, não por ordem alfabética nem por id do seed: a ordem útil é "o que está mais perto de mim agora", e ela muda conforme o professor progride.

Sem desenho geográfico. O SDD é explícito sobre a interface ser lista-e-botão, e um mapa desenhado exigiria coordenadas que o seed não tem e que seriam trabalho manual puro para dez nós.

O estado de cada local é visível sem abrir: visitado, alcançável ou fora de alcance, com a duração ao lado quando faz sentido.

## Riscos

| Risco | Mitigação |
|---|---|
| Usar BFS onde o custo não é uniforme | Dijkstra explícito; teste com masmorra no caminho, onde as duas divergem |
| Pool de encontros vazando pela resposta | schema separado; teste que varre o corpo atrás de espécie não avistada |
| Dijkstra por destino, dez vezes por tela | uma execução multi-origem devolve tudo |
| Estado de um local divergir entre `/map` e `/map/{id}` | a mesma função de domínio alimenta os dois |
| Local isolado no grafo travando a busca | teste de alcançabilidade já existe desde a Fase 1 |

## Fora deste plano

Cache do resultado do Dijkstra — são dez nós, e medir antes de otimizar vale mais que a economia. Coordenadas. Caminho alternativo escolhido pelo professor. Pré-visualização de recompensa.
