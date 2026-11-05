# 001 — Seed de dados do mundo

## Problema

O PokeLab não conhece nenhum Pokémon, nenhum lugar e nenhum item. Sem esse acervo, não há starter para conceder, não há destino para despachar um treinador e não há encontro para resolver. Toda fase seguinte depende deste conjunto de dados existir, estar completo e ser confiável.

O acervo precisa ser estável: o mesmo em desenvolvimento, em teste e no servidor, hoje e daqui a seis meses, sem depender de um serviço externo continuar no ar.

## Comportamento esperado

O mundo do jogo é descrito por um acervo versionado junto com o código: as 151 espécies originais com seus atributos de combate e evolução, dez lugares de Kanto ligados entre si formando um caminho de Pallet Town a Cerulean City, a lista de quais Pokémon aparecem em cada lugar e com que frequência, e os itens que um treinador pode levar na mochila.

O professor nunca edita esse acervo, e o jogo nunca o altera durante a partida. Ele é pano de fundo: muda quando a equipe decide que muda.

Carregar o acervo numa instalação nova é um comando só. Carregar de novo, por cima de uma partida em andamento, atualiza o pano de fundo sem apagar nada do que o professor conquistou.

## Regras

1. O acervo tem exatamente 151 espécies, numeradas de 1 a 151 sem lacuna.
2. Cada espécie traz nome, um ou dois tipos, os seis atributos-base, a experiência que concede ao ser derrotada, a taxa de captura, a curva de crescimento, e a imagem de frente e de costas.
3. Uma espécie que evolui por nível indica para qual espécie evolui e em que nível. Evolução por pedra, troca ou amizade está fora da primeira versão.
4. Os três iniciais — Bulbasaur, Charmander e Squirtle — são marcados como tal.
5. O mundo tem dez lugares. Cada um informa seu tipo, sua dificuldade, a faixa de nível dos Pokémon selvagens que abriga, quanto tempo leva uma expedição até lá, e quais lugares são seus vizinhos.
6. Pallet Town é o único lugar já desbloqueado quando um laboratório nasce.
7. Todo lugar é alcançável a partir de Pallet Town percorrendo vizinhanças.
8. A vizinhança é recíproca: se A é vizinho de B, B é vizinho de A.
9. Todo lugar tem ao menos uma espécie que pode ser encontrada ali, com um peso que define quão comum ela é.
10. Toda espécie citada como encontro existe entre as 151.
11. Toda evolução aponta para uma espécie existente entre as 151.
12. O acervo traz ao menos uma Pokébola, um item de cura e um revive, cada um com sua potência.
13. Carregar o acervo duas vezes seguidas não duplica registro nem muda resultado.

## Critérios de aceite

1. Dado um banco vazio, quando o acervo é carregado, então existem 151 espécies, 10 lugares, pelo menos 6 itens, e pelo menos uma tabela de encontro por lugar.
2. Dado o acervo carregado, quando ele é carregado novamente, então a contagem de registros não muda e nenhum erro ocorre.
3. Dado o grafo de lugares, quando se percorre a partir de Pallet Town, então todos os dez lugares são alcançados.
4. Dada qualquer espécie que evolui, quando se busca o alvo da evolução, então ele existe entre as 151.
5. Dado qualquer lugar, quando se consulta seu pool de encontros, então ele não está vazio e todas as espécies citadas existem.
6. Dada qualquer espécie, quando se busca suas imagens, então ambos os arquivos existem no disco.
7. Dado o ingestor, quando executado duas vezes, então o segundo diff dos arquivos gerados é vazio.
8. Dada a aplicação em execução, quando se inspeciona o código de `api/`, então não há nenhuma chamada a serviço externo.

## Fora de escopo

Movimentos, PP e tabela de efetividade de tipos. Evoluções por pedra, troca ou amizade. Pokémon além dos 151. Lugares além dos dez. Sprites shiny, animados ou de outras gerações. Loja, preço de item e moeda. Encontros condicionais (surfe, pesca, horário).

## Depende de

Fase 0 (concluída).
