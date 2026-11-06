# 006 — Despacho de Expedições

## Problema

Tudo está pronto e nada acontece. Há treinadores com times montados, um mapa com destinos alcançáveis e durações calculadas, itens na mochila — e nenhuma forma de juntar as três coisas. O professor olha para um treinador pronto e para um destino aberto, e não tem botão nenhum.

É também a primeira vez que o jogo vai precisar de **tempo**. Até aqui tudo foi imediato: pede, responde, acabou. Uma expedição é a primeira coisa que começa agora e termina depois, e que precisa continuar correndo com o navegador fechado.

## Comportamento esperado

O professor escolhe um treinador disponível, um destino alcançável e o que mandar na mochila. Antes de confirmar, vê o que a escolha produz: quanto tempo vai levar, quão difícil é o lugar para aquele time, e quantos Pokémon o treinador conseguirá trazer.

Confirmada, a expedição parte. Os itens saem do estoque, o treinador fica ocupado, e um cronômetro começa a correr.

O professor acompanha as expedições em curso e vê quanto falta para cada uma. Fecha o navegador, volta no dia seguinte, e o tempo correu — o jogo não espera por ele.

Pode abortar uma expedição em andamento. O treinador volta na hora, mas os itens que levou não voltam.

Quantas expedições correm ao mesmo tempo é decidido por quantos treinadores estão livres, e nada mais.

## Regras

1. Uma expedição exige um treinador disponível com ao menos um Pokémon no time.
2. O destino deve ser um local alcançável para aquele laboratório.
3. Os itens levados saem do estoque no momento do envio.
4. Não se envia mais itens do que há em estoque.
5. O treinador fica ocupado do envio até o retorno.
6. Um treinador ocupado não entra em outra expedição nem em entrega.
7. O número de expedições simultâneas é limitado apenas pelos treinadores livres.
8. A duração é calculada no envio e não muda depois.
9. O tempo corre no servidor, independentemente de haver alguém olhando.
10. O tempo restante informado é sempre calculado pelo servidor.
11. Abortar devolve o treinador imediatamente e não devolve os itens.
12. Uma expedição abortada não produz resultado nem recompensa.
13. Cada expedição guarda a semente da sua aleatoriedade no envio.
14. Só se vê e opera expedição do próprio laboratório.

## Critérios de aceite

1. Dado um treinador com time e um destino alcançável, quando o professor despacha, então a expedição é criada com previsão de retorno e o treinador fica ocupado.
2. Dado um treinador sem Pokémon no time, quando se tenta despachá-lo, então a operação é recusada explicando o motivo.
3. Dado um treinador já em expedição, quando se tenta despachá-lo de novo, então a operação é recusada.
4. Dado um destino fora de alcance, quando se tenta despachar para lá, então a operação é recusada.
5. Dados três treinadores com time, quando o professor despacha os três, então as três expedições correm simultaneamente.
6. Dados três treinadores todos ocupados, quando se tenta uma quarta expedição, então ela é recusada por falta de treinador.
7. Dada uma carga de duas Poções, quando a expedição parte, então o estoque diminui em duas Poções.
8. Dada uma carga maior que o estoque, quando se tenta despachar, então a operação é recusada e nada é debitado.
9. Dada uma expedição em curso, quando o professor consulta a lista, então vê o tempo restante calculado pelo servidor.
10. Dada uma expedição em curso, quando o professor recarrega a página, então o tempo restante continua coerente.
11. Dada uma expedição cujo tempo acabou, quando o professor consulta, então ela aparece como terminada e aguardando o relatório.
12. Dada uma expedição em curso, quando o professor a aborta, então o treinador fica disponível na hora e os itens não voltam ao estoque.
13. Dada uma expedição de outro professor, quando requisitada pelo identificador, então a resposta é 404.
14. Dada uma mesma expedição, quando despachada duas vezes em paralelo com o mesmo treinador, então apenas uma é criada.

## Fora de escopo

Resolver a expedição e produzir o relatório de campo (é a Fase 7); encontros, batalhas, capturas, experiência, desbloqueio de local; estender ou acelerar uma expedição em curso; reenviar automaticamente; fila de expedições; notificação fora do app; histórico com estatísticas.

A expedição desta fase **parte e expira, e não volta com nada**. Isso é deliberado: a Fase 7 é quem dá sentido ao retorno, e misturar as duas tornaria o motor impossível de testar isoladamente.

## Depende de

Fase 4 (treinadores com time) e Fase 5 (mapa, alcance e duração), ambas concluídas.
