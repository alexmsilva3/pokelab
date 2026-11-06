# 006 — Plano

## Abordagem

Duas coisas novas no projeto, e só a segunda é difícil.

A primeira é mais um CRUD escopado: criar, listar, abortar. Os invariantes já existem no domínio desde as Fases 4 e 5 — `exigir_destino_alcancavel` em `game/mapa.py`, status de treinador em `game/trainers.py`.

A segunda é **tempo**. Até aqui todo endpoint respondia sobre o agora. Uma expedição tem `started_at` e `eta` gravados, e o estado dela depende de comparar o relógio com o `eta`. Isso muda três coisas: o relógio vira parâmetro do domínio (nunca lido lá dentro, Artigo I), o "tempo restante" é sempre do servidor, e aparece pela primeira vez um estado que muda sem ninguém pedir.

## O estado que ninguém pediu

Uma expedição cujo `eta` passou **não é mais `EM_CURSO`**, mesmo que nenhuma linha do banco tenha mudado. Ela está `AGUARDANDO_RELATORIO`: terminou, e falta a Fase 7 resolvê-la.

Esse estado é **derivado, não gravado**. A coluna continua `EM_CURSO` até a Fase 7 escrever o resultado; quem olha calcula a partir do `eta`. Gravar exigiria um job varrendo o banco, e o ADR-004 decidiu explicitamente não ter um na v1.

A consequência de desenho importa: toda leitura que mostra status precisa derivar, e dois lugares derivando diferente seria bug. Por isso a derivação mora em `game/expedition.py`, numa função só.

## Domínio

`game/expedition.py`, puro, com o agora chegando como parâmetro:

```
calcular_despacho(treinador, time, rota, destino, carga, agora, escala) -> DespachoCalculado
    valida invariantes 1, 2, 3, 6, 9 e 17, e devolve duracao, eta, seed, poder e dificuldade

estado_observado(expedicao, agora) -> EM_CURSO | AGUARDANDO_RELATORIO | CONCLUIDA | ABORTADA
tempo_restante(expedicao, agora)   -> segundos, nunca negativo
dificuldade_do_local(local, ...)   -> a seção 4.3, a metade que faltava
chance_estimada(poder_time, dificuldade) -> a sigmoide da seção 4.3
```

`dificuldade_do_local` e `chance_estimada` completam a seção 4.3 — a Fase 4 trouxe só o poder do time. A Fase 7 vai usar as mesmas funções para resolver os encontros de verdade; aqui elas servem à prévia.

A duração reusa `game.mapa.duracao_estimada`, agora com o treinador e a carga reais. Não reimplementar.

## Modelo

```
expedicoes         id, laboratorio_id, treinador_id, local_destino_id, local_origem_id,
                   status, seed, started_at, eta, resolvida_em, duracao_minutos,
                   dificuldade_calculada, poder_time_calculado
expedicao_itens    expedicao_id, item_id, quantidade_levada, quantidade_consumida
expedicao_eventos  id, expedicao_id, ordem, tipo, texto, payload, ocorrido_em_minuto
```

`expedicao_eventos` nasce vazia: é a Fase 7 que a preenche. Criar agora evita uma migração isolada depois, mesmo padrão de `pokedex_avistamentos` na Fase 5.

`status` guarda só o que é fato gravado: `EM_CURSO`, `CONCLUIDA_SUCESSO`, `CONCLUIDA_FALHA`, `ABORTADA`. `AGUARDANDO_RELATORIO` não é valor de coluna.

Índice em `(laboratorio_id, status)`: a consulta de expedições ativas é a mais frequente da tela.

## Contratos de API

```
POST /expeditions   {treinador_id, local_id, carga: [{item_id, quantidade}]}
    201 -> ExpedicaoLer
    409 -> TREINADOR_OCUPADO | TIME_VAZIO | DESTINO_FORA_DE_ALCANCE | ESTOQUE_INSUFICIENTE
    404 -> treinador ou local de outro laboratório / inexistente

GET  /expeditions?status=
    200 -> {items: [ExpedicaoLer], total}

GET  /expeditions/{id}
    200 -> ExpedicaoLer
    404 -> inexistente ou de outro laboratório

DELETE /expeditions/{id}
    200 -> ExpedicaoLer   (status ABORTADA, treinador livre, itens não devolvidos)
    409 -> EXPEDICAO_NAO_ESTA_EM_CURSO

POST /expeditions/preview  {treinador_id, local_id, carga}
    200 -> {duracao_minutos, eta_estimado, dificuldade, chance_estimada,
            capacidade_bagagem, valido, codigo?, motivo?}
```

`ExpedicaoLer` traz `estado_observado` e `segundos_restantes`, ambos calculados no servidor a cada leitura.

A prévia segue o padrão que funcionou na Fase 4: valida sem gravar, usando a **mesma** função do despacho, e devolve o motivo quando recusa.

## Concorrência

Mesmo risco da Fase 4, com um agravante: além de dois despachos disputarem o mesmo treinador, dois despachos podem disputar o **mesmo item do estoque**.

O envio trava, na mesma transação e em ordem determinística por id: a linha do treinador e as linhas de `item_estoques` da carga. O débito é condicional — `UPDATE ... WHERE quantidade >= :n` —, e zero linhas afetadas significa estoque insuficiente, não sucesso silencioso.

## Frontend

```
pages/Expedicoes.tsx            ativas e histórico
components/DespacharExpedicao.tsx   treinador, destino, carga, prévia
components/ContadorRegressivo.tsx
api/expedicoes.ts
```

**O contador é o ponto delicado.** Ele conta localmente para não pedir ao servidor a cada segundo, mas **o servidor é a autoridade**: cada poll traz `segundos_restantes` e corrige a contagem local. Guardar o `eta` e contar sozinho até o fim faria o relógio do cliente decidir quando a expedição acaba — e um relógio adiantado concluiria antes.

Polling leve, só enquanto houver expedição ativa e a aba estiver visível. Nada de intervalo rodando em aba de fundo.

Treinador sem time aparece indisponível, com o motivo e um atalho para montar o time (tarefa 6.7). Destino fora de alcance idem, com atalho para o mapa.

## Riscos

| Risco | Mitigação |
|---|---|
| Dois despachos com o mesmo treinador ou o mesmo item | lock ordenado por id; débito condicional; teste de concorrência com threads |
| Contador decidindo o fim pelo relógio do cliente | servidor manda `segundos_restantes`; teste com relógio adiantado |
| `AGUARDANDO_RELATORIO` derivado em dois lugares diferentes | uma função só em `game/expedition.py`, usada por toda leitura |
| Escala de tempo errada repetindo o erro da Fase 5 | ela MULTIPLICA; teste explícito de que 0.01 encurta |
| Polling rodando em aba de fundo | pausar quando oculta |

## Fora deste plano

Job periódico resolvendo expedições — o ADR-004 decidiu pela resolução preguiçosa. WebSocket. Fila de espera. Reenvio automático.
