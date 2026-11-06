# 007 — Relatório de Campo

## Problema

A Fase 6 entregou uma expedição que parte, consome itens, ocupa um treinador e **expira sem devolver nada**. O professor despacha, espera, e o cronômetro chega a zero diante de uma tela que não tem o que mostrar. Falta exatamente a metade que dá sentido à outra: o que aconteceu lá fora.

É também o primeiro lugar onde o jogo precisa **produzir** em vez de validar. Até aqui todo endpoint respondia uma pergunta sobre o estado atual. Este inventa acontecimentos — e precisa inventar sempre os mesmos, a partir da semente gravada no envio, porque um relatório que muda a cada leitura não é relatório.

## Comportamento esperado

Terminado o prazo, o treinador está de volta à porta do laboratório com um relatório na mão. O professor clica para recebê-lo, e só então o que aconteceu em campo entra nos registros.

O relatório é uma linha do tempo em português: a partida, cada encontro com o que foi enfrentado e se foi vencido, as capturas e as que escaparam, os itens achados pelo caminho, os Pokémon que subiram de nível ou evoluíram, e o retorno. Abaixo dela, o resumo: quem veio junto, quanta experiência cada nível ganhou — Pokémon, treinador e laboratório — e o que saiu da mochila.

Recebido o relatório, o mundo muda. Os Pokémon capturados estão no laboratório. O time voltou machucado. As espécies enfrentadas entraram na Pokédex, e o laboratório agora sabe **onde** cada uma vive. Se correu bem, o destino está desbloqueado e vira ponto de partida das próximas expedições. O treinador está livre.

Se correu mal — três derrotas sem o que curar — o treinador volta mais cedo e de mãos vazias. O relatório existe assim mesmo, e explica a derrota.

Receber o relatório duas vezes não produz dois resultados. O primeiro clique resolve; os seguintes releem o que já ficou gravado.

Enquanto isso, no laboratório, Pokémon machucados se recuperam sozinhos com o passar do tempo. Quem está em campo não se recupera.

## Regras

1. O relatório só é produzido depois que o prazo da expedição venceu.
2. Uma expedição é resolvida **uma única vez**, garantida por lock e checagem de status.
3. O conteúdo do relatório é função apenas da semente e do estado gravado no envio.
4. A quantidade de encontros vem do destino, com variação de um para mais ou para menos.
5. Em cada encontro, a espécie é sorteada pelo peso da tabela do local e o nível na faixa do local.
6. A chance de vitória é recalculada a cada encontro, com o time no desgaste do momento e o nível do selvagem efetivamente sorteado.
7. Uma vitória distribui experiência entre os Pokémon do time, dá um terço do total ao treinador e desgasta o time.
8. Uma derrota desgasta mais, e consome um item de cura se houver.
9. Três derrotas **sem cura disponível** encerram a expedição em falha.
10. Só há tentativa de captura após vitória, com Pokébola na carga e espaço na bagagem.
11. A bagagem comporta `6 − tamanho_do_time` capturas; atingido o limite, o treinador segue registrando na Pokédex.
12. Toda espécie enfrentada entra na Pokédex como vista, capturada ou não, e gera avistamento ligando espécie e local.
13. Nenhum Pokémon ultrapassa o nível 100.
14. A evolução dispara na resolução quando o nível alcança o exigido pela espécie, e encadeia.
15. Uma expedição bem-sucedida desbloqueia o destino e dá experiência ao laboratório.
16. Uma expedição falha não desbloqueia nada, não traz capturas, e mantém a experiência ganha nas batalhas vencidas antes da derrota.
17. Itens consumidos em campo são debitados da carga da expedição, nunca do estoque do laboratório.
18. Itens encontrados em campo entram no estoque do laboratório na resolução.
19. Os Pokémon capturados chegam ao laboratório soltos, não no time do treinador, com o nível que tinham em campo.
20. O treinador volta a `DISPONIVEL` na resolução.
21. No laboratório, `hp_atual_pct` sobe sozinho com o tempo até 100; em expedição, não sobe.
22. Só se resolve e se lê expedição do próprio laboratório.

## Critérios de aceite

1. Dada uma expedição cujo prazo venceu, quando o professor pede o relatório, então recebe uma linha do tempo começando em `PARTIDA` e terminando em `RETORNO`.
2. Dada uma expedição ainda em curso, quando se pede o relatório, então a operação é recusada explicando que o prazo não venceu.
3. Dada a mesma semente e o mesmo estado de envio, quando a resolução roda duas vezes, então produz exatamente os mesmos eventos, na mesma ordem, com os mesmos números.
4. Dada uma expedição vencida, quando dois pedidos de relatório chegam ao mesmo tempo, então apenas um resolve e os dois devolvem o mesmo relatório.
5. Dada uma expedição já resolvida, quando o relatório é pedido de novo, então nada muda no laboratório.
6. Dada uma expedição bem-sucedida com Pokébolas na carga, quando resolvida, então pelo menos um Pokémon pode ser capturado e aparece no laboratório, solto, com o nível de campo.
7. Dado um treinador com time de três, quando a expedição resolve, então são criadas no máximo três capturas, e os avistamentos continuam sendo registrados depois disso.
8. Dada uma carga sem Pokébolas, quando a expedição resolve, então não há captura alguma e há avistamentos.
9. Dada uma vitória, quando a expedição resolve, então cada Pokémon do time ganha experiência e o treinador ganha um terço do total da batalha.
10. Dado um Pokémon que cruza o limiar de nível, quando a expedição resolve, então há evento `SUBIU_NIVEL` e o nível gravado é o novo.
11. Dado um Pokémon que alcança o nível de evolução da espécie, quando a expedição resolve, então há evento `EVOLUCAO` e a espécie gravada é a seguinte.
12. Dado um Pokémon no nível 100, quando a expedição resolve, então ele não passa de 100 e a experiência excedente é descartada.
13. Dada uma expedição bem-sucedida, quando resolvida, então o destino fica desbloqueado e passa a ser origem válida.
14. Dada uma expedição bem-sucedida, quando resolvida, então o laboratório ganha experiência proporcional à dificuldade do destino.
15. Dada uma expedição que acumula três derrotas sem cura, quando resolvida, então termina em `CONCLUIDA_FALHA`, sem capturas e sem desbloqueio.
16. Dada uma derrota com Poção na carga, quando a expedição resolve, então a Poção é consumida, o time recupera HP e a contagem de derrotas recomeça.
17. Dada uma espécie nunca vista, quando é enfrentada, então há evento `DESCOBERTA` e a Pokédex passa a listá-la.
18. Dada uma espécie já vista no mesmo local, quando é enfrentada de novo, então o avistamento soma uma vez e não há `DESCOBERTA`.
19. Dada uma expedição resolvida, quando o professor abre o relatório, então vê a linha do tempo, o resumo de capturas, a experiência dos três níveis e os itens consumidos.
20. Dado um Pokémon machucado no laboratório, quando passa tempo suficiente, então seu HP aparece maior sem nenhuma ação do professor.
21. Dado um Pokémon machucado despachado em expedição, quando a expedição está em curso, então o HP dele não sobe.
22. Dada uma expedição de outro professor, quando se pede o relatório, então a resposta é 404.

## Fora de escopo

Combate turno a turno (ADR-003 mantém a resolução probabilística); evolução por pedra, troca ou amizade (questão 17, tarefa 10.7); limite de armazenamento de Pokémon no laboratório (questão 11, decidida como ilimitada na v1); estado `DESCANSANDO` com prazo — o treinador volta direto a `DISPONIVEL`; notificação de retorno (tarefa 10.2); calibragem dos números (Fase 9); entregas (Fase 8).

## Depende de

Fase 6 (expedição que parte, expira e guarda semente) concluída.
