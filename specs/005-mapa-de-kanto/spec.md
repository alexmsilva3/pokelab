# 005 — Mapa de Kanto

## Problema

O professor tem treinadores com times montados e nenhum lugar para mandá-los. Os dez locais existem no banco desde a Fase 1, ligados por um grafo de vizinhança, e nunca apareceram em tela alguma. Pallet Town está marcada como desbloqueada no laboratório de todo mundo e ninguém sabe disso.

A Fase 6 precisa que o professor escolha um destino, e escolher exige saber três coisas que hoje não existem em lugar nenhum: para onde é possível ir, quanto tempo custa chegar lá, e o que se sabe sobre o lugar.

Há também uma promessa do próprio SDD que nunca foi cumprida: desbloquear um local deveria encurtar as expedições que partem dele. Isso só vale alguma coisa se o professor conseguir ver a diferença antes de despachar.

## Comportamento esperado

O professor abre o mapa e vê os dez lugares de Kanto, em ordem de proximidade do laboratório. Cada um mostra em que pé está: já visitado, alcançável agora, ou ainda fora de alcance.

Para os lugares alcançáveis, vê de onde seus treinadores partiriam e quanto tempo a ida levaria — e percebe, comparando, que partir de um lugar já visitado é mais rápido do que sair de Pallet.

Para os lugares ainda fora de alcance, vê o que falta: qual o próximo lugar a visitar para que aquele se abra.

Abrindo um lugar, vê sua dificuldade, a faixa de nível dos Pokémon selvagens, o tempo estimado, e **quais espécies seus treinadores já encontraram ali**. Um lugar nunca visitado não revela nenhuma espécie: descobrir o que mora lá é trabalho dos treinadores, não informação dada de graça.

## Regras

1. Os dez locais sempre aparecem, qualquer que seja o progresso.
2. Um local está em um de três estados: visitado, alcançável ou fora de alcance.
3. Um local é alcançável se for vizinho de algum local visitado.
4. Um local visitado continua sendo um destino válido — repetir é permitido.
5. Pallet Town está visitada desde a criação do laboratório.
6. O tempo de ida é calculado a partir do local visitado que o torna mais curto.
7. O tempo de ida soma a travessia do caminho e a exploração do destino.
8. Um local fora de alcance informa qual o próximo local a visitar para abri-lo.
9. Um local informa apenas as espécies que os treinadores daquele laboratório já avistaram ali.
10. Um local nunca visitado não revela espécie alguma, nem quantas existem.
11. Dois professores com progressos diferentes veem mapas diferentes.
12. Só se vê o progresso do próprio laboratório.

## Critérios de aceite

1. Dado um laboratório recém-criado, quando o professor abre o mapa, então vê dez locais, com Pallet Town visitada e Route 1 alcançável.
2. Dado um laboratório recém-criado, quando o professor olha Cerulean City, então ela está fora de alcance.
3. Dado um laboratório recém-criado, quando o professor olha Pewter City, então o mapa informa que é preciso visitar Route 1 antes.
4. Dado um local alcançável, quando o professor o consulta, então vê de qual local visitado a ida partiria e quanto tempo levaria.
5. Dado que Route 1 passa a ser visitada, quando o professor reabre o mapa, então Viridian City passa de fora de alcance a alcançável.
6. Dado que Route 1 passa a ser visitada, quando o professor consulta Route 1 de novo, então ela continua sendo um destino válido.
7. Dado que Viridian City passa a ser visitada, quando o professor consulta Route 2, então o tempo de ida é menor do que era quando a origem só podia ser Pallet Town.
8. Dado um local nunca visitado, quando o professor o consulta, então nenhuma espécie é informada e nenhum número de espécies é revelado.
9. Dado um local onde um treinador já avistou uma espécie, quando o professor o consulta, então aquela espécie aparece e as demais do local não.
10. Dado o identificador de um local inexistente, quando requisitado, então a resposta é 404.
11. Dados dois professores com progressos diferentes, quando ambos abrem o mapa, então cada um vê o próprio progresso.
12. Dado qualquer local, quando se inspeciona a resposta, então a tabela de encontros do seed não aparece.

## Fora de escopo

Despachar expedição a partir do mapa (é a Fase 6); desenho geográfico ou coordenadas; rotas alternativas ou escolha manual de caminho; viagem rápida; clima ou horário; locais fora dos dez; marcar favorito; estimativa de recompensa; qualquer coisa que dependa de uma expedição ter acontecido, além da leitura dos avistamentos.

## Depende de

Fase 1 (locais e grafo), Fase 2 (Pallet desbloqueada no kit) e Fase 4 (treinadores, para a estimativa por nível), todas concluídas.
