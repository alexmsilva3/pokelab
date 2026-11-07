# 008 — Viveiro e Central de Entregas

## Problema

A Fase 7 fez o laboratório produzir. Agora ele só acumula: Pokémon entram e nada sai, a moeda não existe, e o treinador só sabe fazer uma coisa. Falta o outro lado do fluxo.

São duas peças que só funcionam juntas. O **viveiro** dá um teto ao que o laboratório guarda — e sozinho seria apenas uma parede. A **Central de Entregas** escoa o excedente pagando por ele — e sozinha seria apenas uma troca opcional que ninguém precisa fazer. Juntas viram a primeira economia do jogo: capturar enche, entregar esvazia e paga, e no meio o professor escolhe quem fica.

É também onde o nível do laboratório deixa de ser um número. Até aqui ele mexia em `limite_treinadores` e em mais nada; a partir daqui ele decide o que a Central pede.

## Comportamento esperado

Os Pokémon que não estão no time de ninguém vivem no viveiro, que tem cinquenta lugares. O professor vê quantos estão ocupados.

Uma expedição volta com o que o treinador conseguiu carregar, caiba ou não. O viveiro transborda, e transbordado ele trava o despacho de expedições novas — nada mais. Reclamar relatório, aceitar entrega e soltar continuam funcionando, porque fechar essas portas seria punir o professor por um problema que ele está tentando resolver.

Para voltar a despachar, ele solta ou entrega até caber. Soltar devolve o Pokémon à natureza e não rende nada; é a saída rápida e cara em outro sentido.

Na Central há sempre três pedidos. Cada um quer de uma a três espécies, em quantidade, entregues numa cidade aberta. O que é pedido depende do nível do laboratório: um laboratório jovem recebe encomendas de Pokémon comuns, um laboratório adiantado recebe encomendas difíceis — inclusive de espécies que o professor nunca viu, que é o jogo dizendo que existe algo lá fora e vale ir buscar.

Cada pedido tem prazo. Vencido sem aceite, sai de circulação e dá lugar a outro — repor o que venceu não custa espera. Descartar a lista inteira por não gostar dela, sim: isso espera quinze minutos.

Ao aceitar, o professor escolhe **quais** Pokémon manda, entre os que atendem ao pedido. Eles ficam comprometidos, o treinador parte, e na volta eles não voltam — saem do laboratório para sempre, em troca de moeda e experiência.

## Regras

1. Pokémon com treinador nulo ocupam lugar no viveiro; os que estão num time, não.
2. O viveiro comporta `CAPACIDADE_VIVEIRO` Pokémon, mas pode transbordar por captura de expedição.
3. Com o viveiro acima da capacidade, nenhuma expedição nova parte.
4. Reclamar relatório, aceitar entrega, concluir entrega e soltar funcionam com o viveiro transbordado.
5. Soltar remove o Pokémon do viveiro ou do time e não rende nada.
6. Não se solta Pokémon em expedição nem comprometido com entrega.
7. O laboratório nunca fica sem nenhum Pokémon.
8. Soltar não apaga nada da Pokédex.
9. A Central mantém `ENTREGAS_DISPONIVEIS` pedidos.
10. Um pedido quer de uma a três espécies distintas, 1 a `QUANTIDADE_MAXIMA_POR_ESPECIE` de cada.
11. A quantidade pedida é ponderada pela taxa de captura da espécie.
12. As espécies candidatas saem da banda de raridade do nível do laboratório.
13. Uma espécie só é pedida se vive em algum local alcançável para aquele laboratório.
14. A Pokédex não participa da geração de pedidos.
15. O destino é sempre uma cidade já desbloqueada.
16. Cada pedido nasce com prazo; vencido, deixa de ser aceitável.
17. A expiração é derivada do relógio e nunca gravada.
18. Repor vaga aberta por expiração ou por aceite não consome o intervalo de regeração.
19. Regerar a lista inteira exige `INTERVALO_REGERAR_ENTREGAS` desde o último sorteio.
20. O aceite recebe os Pokémon escolhidos pelo professor e exige um treinador livre.
21. Os Pokémon escolhidos precisam satisfazer exatamente espécie e quantidade do pedido.
22. Um Pokémon comprometido não entra em time, em expedição nem em outra entrega.
23. A entrega parte sempre do laboratório, e o destino é sempre uma cidade.
24. A conclusão remove os Pokémon em definitivo e credita moeda e experiência.
25. Uma entrega é resolvida uma única vez, garantida por lock e checagem de status.
26. Só se vê e opera viveiro e entrega do próprio laboratório.

## Critérios de aceite

1. Dado um laboratório com Pokémon guardados, quando o professor abre o viveiro, então vê ocupação e capacidade.
2. Dado um time de três num treinador, quando se conta a ocupação, então esses três não contam.
3. Dadas três expedições que voltam com mais capturas do que cabe, quando todas são reclamadas, então todos os Pokémon entram e a ocupação passa da capacidade.
4. Dado o viveiro acima da capacidade, quando se tenta despachar, então a operação é recusada dizendo quantos lugares faltam.
5. Dado o viveiro acima da capacidade, quando se reclama um relatório, se aceita uma entrega ou se solta um Pokémon, então a operação funciona.
6. Dado um Pokémon no viveiro, quando o professor o solta, então ele some e a ocupação cai em um.
7. Dado um Pokémon solto, quando se consulta o saldo e o estoque, então nada mudou.
8. Dado um Pokémon no time de um treinador disponível, quando o professor o solta, então o time encolhe.
9. Dado um Pokémon em expedição, quando se tenta soltá-lo, então a operação é recusada.
10. Dado um Pokémon comprometido com entrega, quando se tenta soltá-lo, então a operação é recusada.
11. Dado um laboratório com um único Pokémon, quando se tenta soltá-lo, então a operação é recusada.
12. Dada uma espécie capturada e depois solta, quando se consulta a Pokédex, então ela continua marcada como vista e capturada.
13. Dado um laboratório recém-criado com a Pokédex vazia, quando a Central gera pedidos, então gera normalmente.
14. Dado um laboratório nível 1, quando a Central gera pedidos, então nenhuma espécie pedida está fora da banda comum.
15. Dado um laboratório de nível alto, quando a Central gera pedidos, então a banda inclui espécies raras.
16. Dada qualquer geração, quando se olha cada espécie pedida, então ela vive em algum local alcançável.
17. Dada qualquer geração, quando se conta as espécies de um pedido, então são no máximo três e distintas.
18. Dado um pedido recém-gerado, quando o prazo vence sem aceite, então ele deixa de ser aceitável.
19. Dado um pedido expirado, quando se consulta o banco, então nenhuma escrita aconteceu por causa da expiração.
20. Dado um pedido expirado, quando se tenta aceitá-lo, então a operação é recusada.
21. Dada uma vaga aberta por expiração, quando o professor repõe, então não há espera.
22. Dada uma lista de pedidos válidos, quando o professor tenta regerar antes do intervalo, então a operação é recusada dizendo quanto falta.
23. Dado um pedido de dois Pidgey e quatro Pidgey no viveiro, quando o professor aceita escolhendo dois, então apenas esses dois ficam comprometidos.
24. Dado um pedido de dois Pidgey, quando o professor tenta aceitar com um Pidgey e um Rattata, então a operação é recusada.
25. Dado um Pokémon comprometido, quando se tenta pô-lo num time ou numa expedição, então a operação é recusada.
26. Dada uma entrega aceita, quando o prazo corre, então o treinador fica indisponível até a conclusão.
27. Dada uma entrega concluída, quando se consulta o laboratório, então os Pokémon entregues não existem mais e o saldo de moedas subiu.
28. Dada uma entrega concluída, quando se consulta o viveiro, então os lugares foram devolvidos.
29. Dada uma entrega vencida, quando dois pedidos de conclusão chegam ao mesmo tempo, então apenas um resolve e nenhum Pokémon é removido duas vezes.
30. Dada uma entrega já concluída, quando se pede a conclusão de novo, então nada muda no laboratório.
31. Dada uma expedição em que a bagagem encheu, quando se lê o relatório, então há um evento dizendo que a captura parou por falta de espaço.
32. Dada uma entrega de outro professor, quando requisitada, então a resposta é 404.

## Fora de escopo

A loja e a expansão do viveiro com moedas (backlog 10.3) — a moeda acumula e não compra nada, deliberadamente, porque o preço precisa dos dados da Fase 9; acompanhar expedição em curso (backlog 10.4); intervir em expedição em curso (backlog 10.5); mapa de distribuição de espécies, que é o que daria ao professor onde procurar o pedido inédito (backlog 10.7); recrutamento de treinadores (backlog 10.2); calibragem dos números (Fase 9).

## Depende de

Fase 7 (expedição que resolve e traz capturas) concluída. Esta fase **não altera o motor de resolução**: o viveiro não limita a captura.
