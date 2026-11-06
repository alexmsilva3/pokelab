# 004 — Plano

## Abordagem

Uma escrita só: `PUT /trainers/{id}/team`. Tudo o mais é leitura.

A escrita é de substituição total, não incremental. `PUT` com a lista completa evita a classe inteira de bugs de "adicionar e remover" — ordem de operações, estado intermediário inválido, dois cliques concorrentes deixando quatro Pokémon no time. O servidor recebe o time que deve existir ao final e decide o que mudar.

O poder do time é a parte que exige cuidado de arquitetura: a tela precisa dele **antes** de salvar, para a escolha ser informada, mas o Artigo II proíbe o cliente de calculá-lo. A saída é um endpoint de prévia, que recebe uma composição hipotética e devolve o que ela valeria.

## Domínio

`game/power.py` — a seção 4.3 do SDD, antecipada da Fase 7 porque a prévia precisa dela agora:

```
poder_pokemon = nivel * (1 + soma_stats_base / SOMA_STATS_BASE_REFERENCIA) * (hp_atual_pct / 100)
poder_time    = soma(poder_pokemon) * (1 + nivel_treinador * BONUS_POR_NIVEL_TREINADOR)
```

Puro, com dataclass de entrada enxuta. A Fase 7 depois só acrescenta a dificuldade e a sigmoide.

`game/team.py` — validação dos invariantes 1 a 6 e 11 e o cálculo de capacidade de bagagem. Recebe a composição pretendida e o estado dos envolvidos, devolve o time validado ou levanta erro de domínio. Nenhuma consulta ao banco: quem busca é o serviço.

`game/trainers.py` já tem nome e avatar da Fase 2. Ganha a curva de nível do treinador e o ganho de um terço por batalha, cujo contrato é definido aqui e consumido na Fase 7.

```
exp_total_para_nivel(n) = EXP_TREINADOR_BASE * (n - 1)^2
```

O deslocamento de um nível existe para que o nível 1 custe zero — mesma forma que `game/laboratorio.py` e as curvas de Pokémon já usam. Sem ele, um treinador recém-contratado nasceria devendo experiência.

## Contratos de API

```
GET /trainers
    200 -> {items: [TrainerResumo]}   sem paginacao: sao tres

GET /trainers/{id}
    200 -> TrainerDetalhe   (time completo, poder, capacidade de bagagem, exp)
    404 -> inexistente ou de outro laboratorio

PUT /trainers/{id}/team   {pokemon_ids: [uuid]}
    200 -> TrainerDetalhe
    404 -> inexistente ou de outro laboratorio
    409 -> TIME_CHEIO | POKEMON_JA_ATRIBUIDO | TREINADOR_OCUPADO |
           POKEMON_COMPROMETIDO | POKEMON_DUPLICADO | POKEMON_DESCONHECIDO

`POKEMON_DESCONHECIDO` cobre id inexistente e id de outro laboratório. Vem como
409 e não 404 de propósito: quem não existe é um item da lista, não o recurso
pedido, e o treinador continua lá. É também por onde a regra de escopo chega ao
domínio sem que ele consulte o banco — o serviço só lhe entrega o que pertence
ao laboratório da sessão, e o resto é desconhecido por construção.

POST /trainers/{id}/team/preview   {pokemon_ids: [uuid]}
    200 -> {poder, capacidade_bagagem, valido, motivo?}
```

A prévia **valida sem gravar** e devolve o motivo quando a composição é inválida — assim a tela mostra "este Pokémon já está com outro treinador" enquanto o professor monta, em vez de depois de clicar em salvar.

`GET /pokemon` ganha o filtro `livre=true`, que combina "sem treinador" e "sem entrega". `atribuido=false` hoje só cobre a primeira metade, e vai divergir quando a Fase 8 existir.

### Por que a prévia é POST

Ela não altera estado, o que sugeriria GET. Mas a entrada é uma lista de até três UUIDs, e isso em query string fica feio e esbarra em limite de tamanho. POST com corpo é o desenho honesto; a semântica de leitura fica documentada no nome.

## Dados

Nenhuma migração. `Treinador` e `PokemonInstancia.treinador_id` existem desde a Fase 2, e `comprometido_entrega_id` fica para a Fase 8.

A escrita do time acontece numa transação com lock nas linhas dos Pokémon envolvidos e do treinador. Sem isso, dois `PUT` concorrentes em treinadores diferentes podem atribuir o mesmo Pokémon aos dois — cada um lê "livre" antes do outro gravar.

## Frontend

```
pages/Treinadores.tsx              lista
components/CartaoTreinador.tsx     nome, avatar, nivel, status, time em miniatura
components/MontarTime.tsx          selecao + previa
components/AvatarTreinador.tsx     iniciais sobre cor, do que game/trainers.py gera
api/trainers.ts
```

A montagem é seleção em lista, sem drag-and-drop. Clicar num Pokémon livre o adiciona; clicar num do time o remove. A prévia atualiza a cada mudança, com a requisição anterior cancelada — o professor clica rápido, e resposta antiga chegando depois da nova mostraria número errado.

Salvar é explícito. Montar sem salvar não muda nada, e sair com alterações pendentes avisa.

A tela mostra as duas consequências lado a lado enquanto o professor escolhe: **poder do time** e **quantas capturas a bagagem comporta**. É o trade-off da seção 4.6 do SDD tornado visível no momento da decisão.

## Riscos

| Risco | Mitigação |
|---|---|
| Dois PUT concorrentes atribuindo o mesmo Pokémon | lock nas linhas dentro da transação; teste de concorrência |
| Prévia divergindo do que o salvamento aceita | ambos chamam a mesma função de `game/team.py` |
| Corrida de prévias mostrando poder de uma composição antiga | AbortController e descarte de resposta obsoleta |
| `atribuido=false` trazendo Pokémon de entrega na Fase 8 | filtro `livre` criado agora, com o conceito certo |
| Poder do time divergir do que a Fase 7 usará | `game/power.py` é a fonte única desde já |

## Fora deste plano

Paginação em treinadores. Ordenação do time. Histórico de composições. Sugestão automática de time — tentador, mas tiraria do professor justamente a decisão que esta fase existe para criar.
