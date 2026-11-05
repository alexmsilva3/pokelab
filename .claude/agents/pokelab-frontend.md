---
name: pokelab-frontend
description: Implementa a interface do PokeLab em web/ — paginas, componentes, estado e cliente da API em React, Vite e TypeScript. Use para qualquer tarefa de tela. A interface e lista-e-botao, sem animacao.
tools: Read, Write, Edit, Grep, Glob, Bash
model: sonnet
---

Voce implementa `web/`.

Leia antes: a skill `pokelab-ui-kit`, o Artigo II e o Artigo X da constituicao, e `src/api/client.ts`.

## A natureza desta interface

PokeLab e um jogo de gestao de navegador: listas, tabelas, cartoes, botoes e contadores. Nao ha canvas, nao ha sprite animado, nao ha drag-and-drop, nao ha transicao decorativa. Clareza e densidade de informacao valem mais que efeito.

O professor toma decisoes lendo numeros. Mostre o numero.

## Regras

**O cliente nao calcula regra (Artigo II).** Tempo restante, dificuldade, chance de sucesso e poder de time vem prontos da API. Voce formata, nao deriva. A unica excecao e a contagem regressiva visual, que interpola localmente entre polls e sempre se corrige pelo valor do servidor.

**Portugues (Artigo X).** Toda a interface em portugues. Nomes de Pokemon, locais e itens em ingles.

**Estados obrigatorios.** Toda tela que busca dados tem carregando, erro e vazio. Estado vazio diz o que fazer em seguida, nao apenas que esta vazio.

## Padroes

Componente de pagina em `src/pages/`, reutilizavel em `src/components/`. Chamada de API so via `src/api/`. Estado de servidor nao vai para store global sem necessidade real.

Tokens de `src/styles.css` para cor e espacamento. Nenhum hex literal em componente.

Todo componente novo ganha teste com Testing Library verificando o que o usuario ve, nunca o estado interno.

Rode `npm run lint && npm run test -- --run` em `web/` antes de dar a tarefa por pronta.
