---
name: pokelab-ui-kit
description: Convencoes de interface do PokeLab — tokens de cor e espacamento, componentes base, vocabulario em portugues do jogo e a regra de que a interface e lista-e-botao sem animacao. Use em qualquer tarefa em web/.
---

# Interface do PokeLab

## A natureza desta interface

Jogo de gestao de navegador. Listas, tabelas, cartoes, botoes e contadores. Sem canvas, sem sprite animado, sem drag-and-drop, sem transicao decorativa.

O professor decide lendo numeros. Mostre o numero, com a unidade, sem arredondar o que importa. "Chance estimada: 68%" vale mais que uma barra colorida.

Densidade acima de respiro: a tela do laboratorio mostra dezenas de Pokemon, e rolar menos e melhor que rolar bonito.

## Tokens

Definidos em `src/styles.css`. Nenhum valor literal de cor ou espacamento em componente.

```
--cor-fundo --cor-superficie --cor-borda
--cor-texto --cor-texto-suave
--cor-acento --cor-acento-texto
--cor-sucesso --cor-alerta --cor-erro
--espaco-1..5   (4, 8, 16, 24, 32 px)
--raio --fonte
```

Tema claro e escuro via `prefers-color-scheme`. Toda cor nova entra como token nos dois temas, nunca so num.

## Componentes base

`Lista` — coluna de itens com cabecalho, filtro e estado vazio.
`Cartao` — superficie com borda e raio, unidade de agrupamento.
`Botao` — variantes `primario`, `secundario`, `perigo`. Acao destrutiva pede confirmacao.
`Contador` — tempo restante de expedicao, atualizado a cada segundo, corrigido pelo servidor a cada poll.
`Timeline` — eventos do relatorio de campo em ordem, com icone por tipo.
`Rotulo` — tipo de Pokemon, status de treinador, estado de local.
`Barra` — HP e progresso de EXP. Sempre acompanhada do numero.

## Estados obrigatorios

Toda tela que busca dados tem carregando, erro e vazio.

O estado vazio diz o que fazer em seguida: "Nenhum treinador no laboratorio. Recrute um para comecar a expedir." — nunca so "Nenhum resultado".

O estado de erro diz o que aconteceu e oferece repetir.

## Vocabulario

| Na interface | Nunca |
|---|---|
| Professor | jogador, usuario |
| Laboratorio | base, home |
| Treinador | NPC, personagem |
| Time | party, equipe |
| Expedicao | missao, run |
| Relatorio de campo | log, resultado |
| Despachar | enviar, iniciar |
| Desbloqueado | liberado, aberto |

Interface em portugues. Nomes de Pokemon, locais e itens em ingles: "Pikachu Nv.12 retornou de Viridian Forest".

## O cliente nao calcula regra

Tempo restante, dificuldade, chance de sucesso e poder de time vem prontos da API (Artigo II). Voce formata, nao deriva.

A unica excecao e a contagem regressiva visual, que interpola localmente entre polls e se corrige pelo valor do servidor a cada resposta.

## Testes

Testing Library, verificando o que o usuario ve. Consulta por papel e texto acessivel, nunca por classe CSS ou estado interno. Nome do teste em portugues descrevendo o comportamento.
