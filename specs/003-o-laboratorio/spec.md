# 003 — O Laboratório

## Problema

O professor entra e vê números: três Pokémon, um treinador, uma localidade. Não vê *quais* Pokémon, não sabe o que eles têm, não consegue distinguir um do outro, e não tem ideia de quanto do mundo ainda falta conhecer. O acervo de 151 espécies e 302 imagens está no repositório desde a Fase 1 e não chegou a nenhuma tela.

Sem isso, as fases seguintes não têm como funcionar: montar um time (Fase 4) exige escolher entre Pokémon que o professor consegue comparar, e escolher um destino (Fase 5) exige saber com o que se está indo.

## Comportamento esperado

O laboratório passa a mostrar seu acervo. O professor vê a lista dos seus Pokémon com imagem, nome, tipo e nível, e consegue encontrar o que procura entre dezenas deles — filtrando por tipo, por faixa de nível, e por estarem ou não com algum treinador.

Clicando num deles, vê a ficha: a imagem grande, os tipos, os atributos já calculados para o nível atual, quanto falta para o próximo nível, de onde aquele indivíduo veio e quando chegou. Pode dar um apelido, e o apelido passa a ser como aquele Pokémon é chamado em toda a interface.

A Pokédex mostra as 151 espécies em ordem. As que o laboratório já capturou aparecem normalmente; as que algum treinador apenas avistou aparecem com a imagem, mas marcadas como não capturadas; as que ninguém nunca viu aparecem como silhueta, sem nome.

O estoque mostra os itens guardados no laboratório, agrupados por categoria. "Estoque" é o do laboratório; o que o treinador leva numa expedição é a mochila dele, e é assunto da Fase 6.

## Regras

1. A lista mostra apenas Pokémon do laboratório do professor da sessão.
2. A lista é paginada, e informa o total para que o professor saiba onde está.
3. Os filtros de tipo, faixa de nível e atribuição combinam entre si.
4. Um Pokémon sem apelido é exibido pelo nome da espécie.
5. O apelido tem entre 1 e 50 caracteres, e apagá-lo devolve o nome da espécie.
6. Os atributos exibidos são os do nível atual do indivíduo, não os da espécie.
7. A ficha mostra quanta experiência falta para o próximo nível; no nível máximo, diz que é o máximo.
8. A Pokédex sempre lista as 151 espécies, qualquer que seja o progresso.
9. Uma espécie nunca vista não revela nome nem tipo — apenas o número e a silhueta.
10. Uma espécie avistada mas não capturada revela nome, tipo e imagem, e é marcada como não capturada.
11. O estoque não mostra item com quantidade zero.
12. As imagens vêm do acervo local, sem nenhuma requisição a serviço externo.
13. Pedir um Pokémon que não existe, ou que é de outro professor, responde como se não existisse.

## Critérios de aceite

1. Dado um laboratório recém-criado, quando o professor abre o laboratório, então vê os três iniciais com imagem, nome, tipo e nível.
2. Dado um laboratório com mais Pokémon do que cabe numa página, quando o professor avança de página, então vê os seguintes e o total não muda.
3. Dado um filtro por tipo, quando aplicado, então apenas Pokémon daquele tipo aparecem, inclusive os que o têm como tipo secundário.
4. Dados filtros de tipo e faixa de nível juntos, quando aplicados, então o resultado satisfaz os dois.
5. Dado um Pokémon de nível 5, quando o professor abre a ficha, então os atributos mostrados são os calculados para o nível 5, e não os da espécie.
6. Dado um Pokémon no nível máximo, quando o professor abre a ficha, então ela informa que não há próximo nível em vez de mostrar um número.
7. Dado um apelido novo, quando salvo, então ele aparece na lista e na ficha; quando apagado, o nome da espécie volta.
8. Dada a Pokédex de um laboratório recém-criado, quando aberta, então tem 151 entradas, três marcadas como capturadas e as demais como desconhecidas.
9. Dada uma espécie nunca vista, quando exibida na Pokédex, então seu nome não aparece em lugar nenhum da resposta nem da tela.
10. Dado o identificador de um Pokémon de outro professor, quando requisitado, então a resposta é 404.
11. Dado o estoque de um laboratório recém-criado, quando aberto, então mostra os itens do kit e nenhum item zerado.
12. Dada qualquer imagem exibida, quando se inspeciona a origem, então ela vem do próprio servidor.

## Fora de escopo

Ordenar a lista por critério escolhido pelo professor; busca por texto; seleção múltipla; liberar ou transferir Pokémon; mover Pokémon entre times (é a Fase 4); ver stats de uma espécie que o laboratório não possui; linha evolutiva na ficha; gráfico de atributos; filtro por origem ou por local de captura; histórico do indivíduo.

## Depende de

Fase 1 (acervo) e Fase 2 (sessão e kit), ambas concluídas.
