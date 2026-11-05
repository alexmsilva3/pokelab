# 002 — Credenciais do Professor

## Problema

O acervo do mundo existe, mas não existe ninguém para jogar. Não há como entrar, não há laboratório, não há de quem sejam os Pokémon. Toda tela e todo endpoint das fases seguintes precisam saber de quem é o estado que estão manipulando, e hoje não há sujeito nenhum.

Além disso, um laboratório recém-criado precisa nascer **capaz de jogar**. Um professor que entra e encontra três Pokémon, nenhum treinador e nenhuma Pokébola não consegue despachar uma única expedição — ficaria preso até a Fase 4 existir.

## Comportamento esperado

Qualquer pessoa pode criar uma conta escolhendo um nome de usuário e uma senha. Ao criar a conta, o laboratório nasce junto, com tudo o que é preciso para o primeiro despacho: três Pokémon iniciais, um treinador contratado, um estoque de Pokébolas e remédios, e Pallet Town já conhecida.

Quem já tem conta entra com usuário e senha e volta ao seu laboratório. A sessão sobrevive a recarregar a página e a fechar o navegador dentro do prazo de validade.

Cada conta tem exatamente um laboratório. O professor nunca vê, nem por acidente, nada que pertença a outro professor.

## Regras

1. O registro é aberto: qualquer um cria uma conta sem convite nem aprovação.
2. O nome de usuário é único, sem diferenciar maiúsculas de minúsculas.
3. A senha tem no mínimo 8 caracteres.
4. A senha nunca é guardada em texto legível e nunca é devolvida por nenhum endpoint.
5. Cada conta tem exatamente um laboratório na v1.
6. O laboratório nasce no nível 1, com zero experiência e zero moedas.
7. Ao criar a conta, o laboratório recebe exatamente uma vez: os três iniciais no nível 5, um treinador no nível 1, o estoque inicial de itens e Pallet Town desbloqueada.
8. Os três iniciais são Bulbasaur, Charmander e Squirtle, e entram na Pokédex como capturados.
9. O treinador inicial chega sem Pokémon no time — montá-lo é decisão do professor.
10. Entrar com senha errada e entrar com usuário inexistente produzem a mesma resposta, sem revelar qual dos dois é o caso.
11. Toda rota de jogo exige sessão válida e só enxerga o laboratório do professor da sessão.
12. Pedir um recurso que existe mas pertence a outro professor responde como se ele não existisse.

## Critérios de aceite

1. Dado nenhum cadastro, quando o professor se registra com um usuário livre, então existem uma conta, um laboratório de nível 1 com zero moedas, três Pokémon de nível 5, um treinador de nível 1, o estoque inicial e Pallet Town desbloqueada.
2. Dado um usuário já cadastrado, quando alguém tenta registrar o mesmo nome em qualquer combinação de maiúsculas, então a operação é recusada com mensagem clara e nada é criado.
3. Dada uma senha com menos de 8 caracteres, quando se tenta registrar, então a operação é recusada e nada é criado.
4. Dadas credenciais corretas, quando o professor entra, então recebe um token de sessão.
5. Dada uma senha errada, quando o professor tenta entrar, então a recusa é idêntica à de um usuário inexistente.
6. Dado um token válido, quando o professor consulta seu perfil, então recebe os dados dele e do laboratório, e nenhum campo de senha.
7. Dada a ausência de token, ou um token inválido ou expirado, quando se chama uma rota protegida, então a resposta é 401.
8. Dados dois professores, quando um tenta acessar um recurso do outro pelo identificador, então a resposta é 404.
9. Dado um registro, quando a criação é disparada duas vezes em paralelo com o mesmo usuário, então apenas uma conta existe ao final e o kit foi concedido uma única vez.
10. Dado um professor autenticado no navegador, quando a página é recarregada, então ele continua dentro sem precisar entrar de novo.
11. Dado qualquer endpoint da aplicação, quando se inspeciona a resposta, então a senha e o hash da senha nunca aparecem.

## Fora de escopo

Recuperação de senha, verificação de e-mail, autenticação federada, dois fatores, renovação automática de token, limite de tentativas de login, perfil editável, exclusão de conta, múltiplos laboratórios por conta, e qualquer tela além de entrar, registrar e o esqueleto do laboratório.

## Depende de

Fase 1 (concluída): o kit inicial precisa das espécies, dos itens e dos locais no banco.
