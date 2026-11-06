# 004 — Corpo de Treinadores

## Problema

O laboratório tem três treinadores e três Pokémon, e nenhuma forma de juntar os dois. Os treinadores existem como linhas no banco desde o kit inicial e não aparecem em tela nenhuma; os Pokémon estão todos parados no laboratório, sem dono.

Sem isso a Fase 6 não tem o que despachar: uma expedição envia um treinador com seu time, e hoje nenhum treinador tem time.

É também aqui que o jogo ganha sua primeira decisão de verdade. Distribuir três Pokémon entre três treinadores não é arrumação: um treinador com os três vence mais encontros e volta com menos capturas, porque a bagagem é o que sobra do time; três treinadores com um cada capturam muito mais e arriscam perder a expedição. O professor escolhe, e a tela precisa deixar a escolha visível antes que ela seja feita.

## Comportamento esperado

O professor vê seus treinadores: nome, retrato, nível, o que cada um está fazendo, e quem já está com ele.

Abrindo um treinador, monta o time escolhendo entre os Pokémon livres do laboratório. Enquanto escolhe, vê o que a escolha produz: o poder do time que está formando, e quantos Pokémon aquele treinador ainda conseguirá trazer de uma expedição.

Um treinador ocupado — em expedição ou em entrega — não aceita mudança de time, e a tela diz por quê em vez de só desabilitar o botão.

Nesta versão não se contrata nem se dispensa ninguém: o corpo de treinadores é o que veio com o laboratório.

## Regras

1. O laboratório nasce com três treinadores e três Pokémon iniciais.
2. Um treinador tem no máximo três Pokémon no time.
3. Um Pokémon pertence a no máximo um treinador por vez.
4. Um treinador ocupado não tem o time alterado.
5. Um Pokémon de treinador ocupado não é retirado do time.
6. Um Pokémon comprometido com uma entrega não entra em time.
7. A capacidade de bagagem de um treinador é seis menos o tamanho do seu time.
8. O poder do time é calculado pelo servidor e considera nível, atributos da espécie, dano acumulado e o nível do treinador.
9. Definir o time substitui o time inteiro: o que não foi listado volta ao laboratório.
10. Um treinador sem Pokémon é estado válido — é como todos começam.
11. Só se vê e altera treinador do próprio laboratório.
12. Não há contratação nem dispensa nesta versão.

## Critérios de aceite

1. Dado um laboratório recém-criado, quando o professor abre os treinadores, então vê três, todos de nível 1, sem Pokémon, disponíveis.
2. Dado um treinador disponível, quando o professor lhe atribui dois Pokémon livres, então o time passa a ter esses dois e eles somem da lista de livres.
3. Dado um treinador com time de dois, quando o professor define um time de um, então o Pokémon que saiu volta a ficar livre.
4. Dada uma lista com quatro Pokémon, quando se tenta definir o time, então a operação é recusada e o time anterior permanece.
5. Dado um Pokémon já no time de outro treinador, quando se tenta atribuí-lo, então a operação é recusada e nada muda nos dois times.
6. Dado um treinador em expedição, quando se tenta alterar seu time, então a operação é recusada com motivo explícito.
7. Dado um treinador com time de três, quando o professor vê sua ficha, então a capacidade de bagagem exibida é três.
8. Dado um treinador com time de um, quando o professor vê sua ficha, então a capacidade de bagagem exibida é cinco.
9. Dados dois times com os mesmos Pokémon mas treinadores de níveis diferentes, quando se compara o poder, então o do treinador de nível maior é maior.
10. Dado o identificador de um treinador de outro professor, quando requisitado, então a resposta é 404.
11. Dada uma lista com o mesmo Pokémon repetido, quando se tenta definir o time, então a operação é recusada.
12. Dado um time definido, quando a página é recarregada, então o time continua o mesmo.

## Fora de escopo

Contratar, dispensar ou perder treinador; ordenar o time; escolher qual Pokémon lidera; apelidar treinador; itens equipados no treinador; especialização por tipo; ver histórico de expedições do treinador; qualquer coisa que dependa de uma expedição ter acontecido.

## Depende de

Fase 2 (kit com os três treinadores) e Fase 3 (lista de Pokémon do laboratório), ambas concluídas.
