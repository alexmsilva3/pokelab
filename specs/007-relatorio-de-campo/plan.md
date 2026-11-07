# 007 — Plano

## Duas decisões antes do código

### ADR-006 — O relatório é reclamado, não derivado numa leitura

A tarefa 7.7 do SDD pedia resolução preguiçosa dentro do `GET /expeditions/{id}`. Fica revista: **a resolução mora em `POST /expeditions/{id}/claim`**, e os `GET` permanecem leituras puras.

Três motivos. Um `GET` que escreve torna `GET /expeditions` ambíguo — listar dez expedições vencidas resolveria as dez numa requisição, com dez locks, e um timeout no cliente ficaria indistinguível de uma repetição. Um `GET` que escreve também impede qualquer cache e qualquer réplica de leitura, por um ganho que é só de uma chamada. E, sobretudo, receber o relatório **é um momento do jogo**, não encanamento: é quando o professor lê o que aconteceu. Dar a ele um verbo próprio dá à interface onde pendurar a linha do tempo, e ao jogador o gesto que o modelo de frota do No Man's Sky sempre teve.

O ADR-004 continua de pé: não há job, não há agendador. A resolução segue acontecendo sob demanda, dentro de uma requisição.

O preço aceito é que o treinador fica ocupado até o professor voltar. É pressão de design, não defeito.

### Recuperação passiva de HP (SDD 4.8, sem fase até aqui)

A seção 4.8 promete que o Pokémon se recupera sozinho no laboratório, e nenhuma fase tinha a tarefa. Sem ela esta fase entrega um loop que trava: o desgaste é de 3 a 8 pontos por vitória e de 15 a 30 por derrota, o poder do time multiplica por `hp_atual_pct / 100`, e em quatro expedições o time chega a zero e não vence mais nada. A cura entra aqui porque é aqui que o dano nasce.

O mecanismo acompanha o ADR-004 — derivado do relógio, nada de job:

```
hp_recuperado(hp_atual_pct, atualizado_em, agora) =
    min(100, hp_atual_pct + (minutos_decorridos // MINUTOS_POR_PONTO_DE_HP))
```

Uma coluna nova, `hp_atualizado_em`, marca desde quando conta. O despacho **materializa** o HP recuperado e carimba `started_at` — em campo o relógio da enfermaria para. A resolução grava o HP desgastado e carimba `resolvida_em` — a recuperação recomeça. Toda leitura deriva. O desgaste da expedição incide sobre o valor materializado no despacho, não sobre o do banco em outro instante, e é por isso que a resolução continua sendo função só da semente e do envio.

## Fronteira

Tudo que decide mora em `app/game/`. A resolução inteira é uma função pura:

```
resolver(contexto: ContextoDeResolucao, gerador: GeradorAleatorio) -> RelatorioDeCampo
```

`ContextoDeResolucao` é um retrato imutável do envio: time (espécie, nível, experiência, HP, curva, stats-base, evolução), nível do treinador, local de destino (dificuldade, faixa de nível, encontros-base, tabela de encontros com peso), carga restante por item, as espécies já vistas **segundo o retrato gravado no despacho** (`expedicoes.especies_vistas_no_envio`, nunca uma leitura da Pokédex no `claim`), duração em minutos. `RelatorioDeCampo` traz os eventos em ordem, o estado final de cada Pokémon do time, as capturas, o consumo por item, os itens achados, os avistamentos, a experiência do treinador e do laboratório, e o status final.

O serviço não decide nada: abre transação, trava a linha, monta o contexto, chama `resolver`, grava o que voltou. Essa separação é o que torna o critério 3 testável sem banco.

## Ordem dos sorteios

A ordem é contrato. Mudá-la muda o resultado de toda semente já gravada, e por isso fica fixada em teste:

```
1  quantidade de encontros        randint(-1, +1) sobre encontros_base
   para cada encontro:
2    espécie                      sorteio por peso acumulado com random()
3    nível do selvagem            randint(nivel_min, nivel_max) da linha
4    vitória ou derrota           random() < p_vitoria do momento
     se vitória:
5      desgaste                   randint(3, 8)
6      achado de item             random() < CHANCE_ITEM_POR_VITORIA
7      qual item                  sorteio por peso na tabela de achados
8      tentativa de captura       random() < p_captura
     se derrota:
5'     desgaste                   randint(15, 30)
```

Experiência, subida de nível e evolução são determinísticos e não consomem sorteio.

## Chance por encontro

A dificuldade gravada no despacho usa o **nível médio** do local e é o que a prévia mostra: uma estimativa, e a interface a rotula assim. A resolução usa o nível efetivamente sorteado e o time no desgaste do momento:

```
dificuldade_encontro = nivel_selvagem_sorteado * nivel_dificuldade_local * FATOR_DIFICULDADE
p_vitoria            = chance_estimada(poder_do_time(time_corrente), dificuldade_encontro)
```

O relatório guarda a chance de cada encontro no payload do evento, para que a derrota seja explicável. O docstring de `expedition.py` que promete coincidência exata com o número do despacho precisa ser corrigido junto.

## Cura e falha

Uma derrota consome o item de cura de menor potência que resolva o caso, nesta ordem: `REVIVE` se houver alguém nocauteado, senão a `CURA` de menor potência disponível. O item restaura `potencia` pontos de `hp_atual_pct` — ao time todo, no caso da cura; ao nocauteado, no caso do revive.

Consumir cura **zera a contagem de derrotas**, porque a regra 9 do SDD fala em três derrotas *sem itens de cura*. Três derrotas consecutivas sem nada para consumir encerram em `CONCLUIDA_FALHA`.

## Experiência

```
exp_da_batalha  = experiencia_base_derrotado * nivel_derrotado // DIVISOR_EXP
exp_por_pokemon = exp_da_batalha // tamanho_do_time
exp_treinador  += exp_da_batalha // 3
```

Participantes é o time inteiro, nocauteado incluído — ele estava lá. A divisão inteira trunca de propósito: experiência é contador, não medida.

Laboratório, só em sucesso: `EXP_LAB_POR_EXPEDICAO * (1 + nivel_dificuldade * BONUS_EXP_LAB_POR_DIFICULDADE)`.

O nível 100 é teto duro: a experiência acima do necessário para 100 é descartada no momento de gravar, e não há evento `SUBIU_NIVEL` para um nível que não subiu.

## Evolução

Depois de aplicada a experiência, enquanto `evolui_para_id` existir e `nivel >= evolui_em_nivel`, a espécie avança. Encadeia — um Bulbasaur que salte do 15 ao 33 numa expedição vira Venusaur, com dois eventos. O laço tem teto de `EVOLUCOES_MAXIMAS_POR_EXPEDICAO` como guarda contra dado circular no seed.

## Achados de item

Nova regra, tarefa 7.6 do SDD. Após cada vitória, uma rolagem de `CHANCE_ITEM_POR_VITORIA` decide se houve achado; havendo, o item sai de uma tabela ponderada em que a Pokébola é comum e a cura é rara, e a quantidade cresce com a dificuldade do local:

```
quantidade = 1 + (nivel_dificuldade_local // DIFICULDADE_POR_ITEM_EXTRA)
```

Os achados entram no **estoque do laboratório** na resolução, não na carga — o treinador já está voltando.

## Migração

Duas, nesta ordem.

| Migração | Coluna | Tipo | Backfill das linhas existentes |
|---|---|---|---|
| `20261106_2300` | `pokemon_instancias.hp_atualizado_em` | `timestamptz NOT NULL` | `now()` — "a recuperação destas começa a contar agora" |
| `20261106_2300` | `expedicoes.relatorio_resumo` | `jsonb NULL` | nenhum: nulo até resolver |
| `20261107_0221` | `expedicoes.especies_vistas_no_envio` | `jsonb NOT NULL` | `'[]'` |

Nas duas colunas `NOT NULL` o default no servidor existe só para o backfill e é removido em seguida, para que um `INSERT` futuro que esqueça a coluna quebre alto em vez de gravar um valor plausível em silêncio. `relatorio_resumo` nasce anulável e sem default, porque "ainda não resolvida" é estado legítimo. Cada `downgrade` derruba o que a sua migração criou.

A segunda migração não estava prevista: veio da revisão da fase. `_montar_contexto` lia a Pokédex viva no instante do `claim`, fora de qualquer lock — o relatório deixava de ser função só da semente e do envio (invariante 19), e dois `claim`s concorrentes do mesmo laboratório liam a Pokédex "antes de qualquer um gravar" e anunciavam a mesma `DESCOBERTA` duas vezes. `especies_vistas_no_envio` grava o retrato no despacho e o `claim` passa a ler só essa coluna.

O backfill com lista vazia é a única opção honesta: não há como saber retroativamente o que uma expedição já em curso conhecia ao partir. Na pior hipótese uma dessas linhas antigas repete uma `DESCOBERTA` que a Pokédex atual já tem — inócuo, e nunca o contrário.

A consequência observável dessa troca está na spec (regra 12, critérios 17, 18 e 23) e no SDD 4.7: uma espécie descoberta depois do despacho continua sendo anunciada como novidade quando aquela expedição é reclamada. Escolha deliberada — um relatório que não muda conforme a hora do clique vale mais que um texto ocasionalmente redundante.

## Endpoint

```
POST /expeditions/{id}/claim  ->  200 RelatorioLer
```

Transação única com `SELECT ... FOR UPDATE` na expedição. Se `status != EM_CURSO`, devolve o relatório gravado sem escrever nada. Se `eta > agora`, recusa com `EXPEDICAO_EM_CURSO`. Caso contrário resolve, grava tudo e devolve.

O `GET /expeditions/{id}` ganha o relatório no corpo quando já existe, e nada mais muda nele.

## Interface

Uma tela nova, `RelatorioDeCampo`, alcançada do painel de expedições quando o estado observado é `AGUARDANDO_RELATORIO` (botão "Receber relatório") ou terminal (botão "Ver relatório"). Lista e botão, como o resto: a linha do tempo é uma lista ordenada com o minuto à esquerda e o texto à direita, ícone por tipo de evento em caractere, sem animação.

## Risco

O maior é silencioso: uma mudança futura na ordem dos sorteios reescreve o passado de toda expedição não resolvida. O teste de ordem fixa existe para quebrar ruidosamente quando isso acontecer.

## Contratos de API

Esta seção é a verdade para os dois lados. Frontend e backend não inventam campo.

### `POST /expeditions/{id}/claim` → 200

```jsonc
{
  "expedicao": { /* ExpedicaoLer, como hoje, com status já terminal */ },
  "relatorio": {
    "status": "CONCLUIDA_SUCESSO",      // ou CONCLUIDA_FALHA
    "resolvida_em": "2026-11-06T18:40:00Z",
    "encontros": 5,
    "vitorias": 4,
    "derrotas": 1,
    "local_desbloqueado": true,          // false em falha ou se já estava aberto
    "eventos": [
      {
        "ordem": 0,
        "tipo": "PARTIDA",
        "texto": "Ash partiu de Pallet Town rumo a Viridian Forest.",
        "ocorrido_em_minuto": 0,
        "payload": null
      },
      {
        "ordem": 1,
        "tipo": "BATALHA",
        "texto": "Bulbasaur enfrentou Caterpie (nivel 5) e venceu.",
        "ocorrido_em_minuto": 3,
        "payload": {
          "especie_id": 10, "especie_nome": "Caterpie", "nivel_selvagem": 5,
          "venceu": true, "chance": 0.72, "exp_da_batalha": 28
        }
      }
    ],
    "capturas": [
      { "especie_id": 10, "especie_nome": "Caterpie", "nivel": 5, "pokemon_id": "uuid" }
    ],
    "time": [
      {
        "pokemon_id": "uuid", "especie_id": 1, "especie_nome": "Bulbasaur",
        "nivel_antes": 5, "nivel_depois": 7, "exp_ganha": 112,
        "hp_antes_pct": 100, "hp_depois_pct": 74,
        "evoluiu_para_id": null, "evoluiu_para_nome": null
      }
    ],
    "treinador": { "nivel_antes": 1, "nivel_depois": 2, "exp_ganha": 64 },
    "laboratorio": { "nivel_antes": 1, "nivel_depois": 1, "exp_ganha": 160 },
    "itens_consumidos": [ { "item_id": "poke-ball", "nome": "Poke Ball", "quantidade": 3 } ],
    "itens_encontrados": [ { "item_id": "potion", "nome": "Potion", "quantidade": 1 } ],
    "especies_vistas": [ { "especie_id": 10, "nome": "Caterpie", "primeira_vez": true } ]
  }
}
```

Recusas, todas 409 com código: `EXPEDICAO_EM_CURSO` (o prazo não venceu), `EXPEDICAO_ABORTADA`. Expedição de outro laboratório: 404.

Uma segunda chamada numa expedição já resolvida devolve **o mesmo corpo**, com status 200 e sem escrever nada.

### `GET /expeditions/{id}` → 200

Ganha `"relatorio": { ... } | null`. Nulo enquanto não resolvida. Nenhum outro campo muda, e a rota continua sem escrever.

### `GET /expeditions` → 200 (revisão pós-Fase 7, achados 1 e 2)

Dois ajustes de contrato, depois de medir ~2 KB por expedição numa listagem real de relatórios de 2 encontros e 9 eventos.

**`items` não é mais `ExpedicaoLer`.** É `ExpedicaoResumoLer`: os mesmos campos de sempre (`id`, `treinador_id`, locais, `status`, `estado_observado`, `seed`, `started_at`, `eta`, `resolvida_em`, duração, dificuldade, poder, `segundos_restantes`, `carga`) **sem** `relatorio`. Com 200 expedições resolvidas, cada abertura do painel serializava 200 linhas do tempo completas — `eventos`, `texto` e `payload` inclusos — que ninguém olhava na lista. Quem quer o relatório pede a ficha (`GET /expeditions/{id}`, que continua `ExpedicaoLer` com `relatorio`) ou reclama (`POST /expeditions/{id}/claim`). A lista diz QUE há relatório através de `estado_observado`/`status`; o conteúdo só sai sob pedido explícito de uma expedição.

**Ganha `limite` na query string**, inteiro, padrão 20, teto 100 (422 acima disso). Decisão: parâmetro com teto, não paginação por cursor. O painel sempre quer "as N expedições mais recentes deste laboratório" — nunca "a página 7" — e um cursor existiria só para resolver um caso de uso que a interface não tem. O corte acontece **na consulta**, antes do filtro por `status`: a resposta é "as `limite` mais recentes, dentre as quais estas batem o filtro", não "as `limite` que batem o filtro em todo o histórico". Na prática isso nunca incomoda o painel de ativas — uma expedição `EM_CURSO`/`AGUARDANDO_RELATORIO` é sempre recente por construção — e o histórico pode pedir um `limite` maior quando precisar enxergar mais para trás.

**`seed` é serializado como STRING**, em `ExpedicaoResumoLer`, `ExpedicaoLer` e em toda resposta que carregue um dos dois (claim incluso). `balance.SEED_MAXIMO = 2**63 - 1` estoura os 2^53-1 bits seguros do `number` do JavaScript; uma semente real como `3500104150819416180` chegava ao navegador como `3500104150819416000` — precisão perdida antes mesmo do primeiro `JSON.parse`, o que quebra silenciosamente o Artigo III (reproduzir um relatório a partir da semente). Decisão: manter o campo (ele tem uso — depuração e a promessa de reprodutibilidade), só mudando o tipo de serialização; nenhum outro campo da API carrega um inteiro fora da faixa segura, então a troca fica isolada a `seed`. **Efeito no frontend:** `RelatorioDeCampo`/`ExpedicaoLer.seed` em `web/src/api/tipos.ts` passa de `number` para `string`; nenhuma aritmética é esperada sobre este campo, só exibição/depuração.

### Leituras de Pokémon

`hp_atual_pct` passa a ser o **valor derivado** (já recuperado até agora), em toda rota que devolve Pokémon — lista, ficha, time de treinador. O valor cru do banco não aparece na API. Acrescenta-se `hp_atualizado_em` para a interface poder explicar a recuperação, e nada mais muda de forma.

### Tipos no frontend

`web/src/api/tipos.ts` ganha `RelatorioDeCampo`, `EventoDeExpedicao`, `TipoDeEvento`, `CapturaDoRelatorio`, `PokemonDoRelatorio`, `GanhoDeExperiencia` e `ItemDoRelatorio`. `web/src/api/fixtures.ts` ganha a fixture tipada de cada um — todo mock de teste sai de lá.

`TipoDeEvento` é a união fechada: `PARTIDA | BATALHA | CAPTURA | CAPTURA_FALHA | DESCOBERTA | ITEM | CONTRATEMPO | SUBIU_NIVEL | EVOLUCAO | RETORNO`.
