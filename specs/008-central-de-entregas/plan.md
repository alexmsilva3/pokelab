# 008 — Plano

## O que esta fase não faz

Não toca o motor de resolução da Fase 7. Uma versão anterior desta regra travava `slots_captura` pelo espaço livre no viveiro, e isso teria alcançado `game/capture.py`, o `ContextoDeResolucao` e o despacho. A regra mudou: o viveiro transborda, e a guarda vive no despacho, que é código desta fase. `resolver()` fica como está.

A única exceção é aditiva: o evento de bagagem cheia (tarefa 3). Ele não consome sorteio, então a ordem do contrato de 4.5 permanece e nenhuma semente muda de resultado — mas muda a sequência de eventos que resoluções futuras produzem, e os testes de determinismo precisam acompanhar.

## O transbordo

A ocupação é derivada, não gravada: `count(*)` dos Pokémon do laboratório com `treinador_id` nulo. Nada de contador materializado — ele divergiria no primeiro caminho que esquecesse de atualizar, e o número é barato com índice.

A guarda é uma só, no despacho:

```
if ocupacao_do_viveiro(laboratorio) > CAPACIDADE_VIVEIRO:
    recusa VIVEIRO_TRANSBORDADO, dizendo quantos lugares faltam
```

Em lugar nenhum mais. Reclamar, aceitar entrega, concluir entrega e soltar não consultam a capacidade. A tentação de "proteger" também esses caminhos precisa ser resistida: eles são as saídas, e fechar a saída de quem está preso é o defeito que a regra 4 existe para proibir.

## Soltar

`DELETE /pokemon/{id}`. Remove a linha de verdade — não há *soft delete*, porque não há para que voltar: não rende nada, não entra em histórico, e um Pokémon solto não é um Pokémon arquivado.

As guardas moram no domínio (invariantes 24 e 25):

```
soltar_permitido(pokemon, treinador, total_do_laboratorio) ->
    POKEMON_EM_EXPEDICAO      se o treinador dele está EM_EXPEDICAO
    POKEMON_COMPROMETIDO      se comprometido_entrega_id não é nulo
    ULTIMO_POKEMON            se total_do_laboratorio == 1
```

`ULTIMO_POKEMON` é a guarda que impede um beco sem saída permanente: sem Pokémon não há time, sem time não há expedição, e sem expedição não há como obter outro. Os iniciais são concedidos uma vez só (invariante 10) e essa porta não reabre. A mesma guarda vale no aceite de entrega.

A Pokédex não é tocada. `visto`, `capturado` e os avistamentos sobrevivem — o professor soltou o bicho, não desaprendeu o que ele era.

## Banda de raridade

```
raridade(especie) = taxa_captura          # 3 (Mewtwo) a 255 (Caterpie), mediana 75
banda(nivel_lab)  = [teto_de_raridade(nivel), 255]
```

Taxa **alta** é espécie comum, então a banda é um piso que **desce** conforme o laboratório sobe: nível 1 só alcança o topo da escala, e cada nível estende para baixo, na direção do raro. Escrever isso ao contrário é o erro provável, e o teste de tabela existe para pegá-lo.

As candidatas são a interseção de três conjuntos:

```
candidatas = espécies dentro da banda
           ∩ espécies que aparecem em LocalEncontro de algum local alcançável
           ∩ (a Pokédex NÃO entra aqui)
```

Alcançável é a mesma noção de `game/mapa.py::exigir_destino_alcancavel`: desbloqueado, ou vizinho de desbloqueado. Sem esse filtro o gerador pede Dragonite a quem está em Pallet, e isso não é objetivo, é ruído.

Interseção vazia é possível em teoria e precisa de resposta deliberada — não de exceção vazando para a tela. Decidir e documentar: alargar a banda até achar candidata é a saída provável, e nesse caso o alargamento precisa ser determinístico.

## Prazo e reposição

`EXPIRADA` é estado observado, derivado de `expira_em` contra o relógio, por uma função única — o terceiro uso do padrão, depois de `AGUARDANDO_RELATORIO` e do HP recuperado. A coluna `status` continua `DISPONIVEL`. Ninguém grava expiração, e o teste prova isso consultando a coluna.

A reposição distingue dois gestos que a mesma rota atende:

```
POST /deliveries/refresh
  vagas = ENTREGAS_DISPONIVEIS - pedidos válidos e não expirados
  se vagas > 0: preenche as vagas, SEM tocar no relógio do intervalo
  se vagas == 0: é descarte da lista válida -> exige INTERVALO_REGERAR_ENTREGAS
```

O intervalo existe contra rolar a sorte até sair o pedido conveniente. Oferta que venceu sozinha não é rolagem, e cobrar por ela puniria quem esperou.

## Entrega

Modelos como na seção 3.2 do SDD. `PokemonInstancia.comprometido_entrega_id` já está previsto no modelo desde a Fase 2 e entra agora.

**Aceite** — transação única, travando em ordem determinística por id: o treinador, e os Pokémon escolhidos. Valida que o conjunto escolhido satisfaz exatamente espécie e quantidade do pedido, que todos estão no viveiro e livres, que o pedido não expirou e que o treinador está disponível. Grava `comprometido_entrega_id`, põe o treinador em `EM_ENTREGA` e calcula `eta`.

**Conclusão** — `POST /deliveries/{id}/claim`, mesmo padrão do ADR-006 e do Artigo VII: `SELECT ... FOR UPDATE`, checagem de status **depois** do lock, segunda chamada devolve o resultado gravado sem escrever.

É a **primeira operação destrutiva do jogo**. Na expedição, resolver duas vezes duplicaria ganho; aqui apagaria Pokémon que não deviam sair, e isso é irreparável. O teste de concorrência conta linhas no banco, nunca a resposta HTTP.

## Duração e recompensa

```
duracao = tempo_viagem(laboratorio, destino) * MULTIPLICADOR_IDA_E_VOLTA
        * (1 - min(nivel_treinador * REDUCAO_POR_NIVEL_TREINADOR, REDUCAO_MAXIMA_TREINADOR))
        * EXPEDITION_TIME_SCALE

moedas = soma, por Pokémon entregue, de
         (MOEDA_BASE + nivel * MOEDA_POR_NIVEL) * (1 + tempo_viagem / 30)
```

`EXPEDITION_TIME_SCALE` **multiplica**. O SDD já errou isso uma vez, na Fase 5.

## Contratos de API

### `GET /ranch` → 200

```jsonc
{
  "capacidade": 50,
  "ocupacao": 52,
  "transbordado": true,
  "lugares_faltando": 2,          // 0 quando não transbordado
  "items": [ /* PokemonLer, como em GET /pokemon */ ]
}
```

### `DELETE /pokemon/{id}` → 204

Recusas 409: `POKEMON_EM_EXPEDICAO`, `POKEMON_COMPROMETIDO`, `ULTIMO_POKEMON`. Outro laboratório: 404.

### `GET /deliveries` → 200

```jsonc
{
  "items": [{
    "id": "uuid",
    "titulo": "Encomenda para Cerulean City",
    "local_destino_id": "cerulean-city",
    "local_destino_nome": "Cerulean City",
    "estado_observado": "DISPONIVEL",        // DISPONIVEL | EXPIRADA | EM_CURSO | CONCLUIDA | DESCARTADA
    "segundos_para_expirar": 7200,            // null quando não é DISPONIVEL
    "requisitos": [
      { "especie_id": 16, "especie_nome": "Pidgey", "quantidade": 2, "disponiveis_no_viveiro": 4 }
    ],
    "atendivel": true,
    "motivo": null,                           // por que não dá para aceitar hoje
    "duracao_minutos": 12,
    "recompensa_moedas": 240,
    "recompensa_exp_laboratorio": 160,
    "recompensa_exp_treinador": 40,
    "eta": null, "segundos_restantes": null, "treinador_id": null
  }],
  "vagas_para_repor": 1,
  "segundos_para_regerar": 420                // 0 quando já pode descartar a lista válida
}
```

### `POST /deliveries/refresh` → 200

Mesmo corpo do `GET`. Recusa 409 `AGUARDE_PARA_REGERAR` com os segundos que faltam, **apenas** quando não há vaga a repor.

### `POST /deliveries/{id}/accept` → 200

```jsonc
{ "treinador_id": "uuid", "pokemon_ids": ["uuid", "uuid"] }
```

Recusas 409: `ENTREGA_EXPIRADA`, `TREINADOR_OCUPADO`, `POKEMON_NAO_ATENDE_AO_PEDIDO`, `POKEMON_INDISPONIVEL`, `ULTIMO_POKEMON`.

### `POST /deliveries/{id}/claim` → 200

```jsonc
{
  "entrega": { /* como acima, estado CONCLUIDA */ },
  "resultado": {
    "pokemon_entregues": [{ "especie_nome": "Pidgey", "nivel": 4 }],
    "moedas_ganhas": 240,
    "moedas_total": 1240,
    "laboratorio": { "nivel_antes": 2, "nivel_depois": 2, "exp_ganha": 160 },
    "treinador": { "nivel_antes": 3, "nivel_depois": 3, "exp_ganha": 40 },
    "lugares_liberados": 2
  }
}
```

Recusa 409 `ENTREGA_EM_CURSO` antes do prazo. Segunda chamada devolve o mesmo corpo sem escrever.

### Despacho de expedição

`POST /expeditions` ganha a recusa 409 `VIVEIRO_TRANSBORDADO`, com `lugares_faltando` nos detalhes.

### Tipos no frontend

`tipos.ts` ganha `Viveiro`, `EntregaLer`, `RequisitoLer`, `ResultadoDeEntrega`, `EstadoObservadoEntrega`. `fixtures.ts` ganha a fixture tipada de cada um.

## Risco

O maior é a guarda do transbordo escapar para os caminhos de saída. Uma recusa a mais em `claim`, em `accept` ou em `DELETE /pokemon` prende o professor sem saída, e o sintoma é um jogador travado sem entender por quê — não um erro no log.
