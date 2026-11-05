---
name: pokelab-spec
description: Formato e disciplina dos artefatos de spec-driven development do PokeLab (spec.md, plan.md, tasks.md). Use antes de abrir qualquer feature nova, ao revisar uma spec existente, ou quando a implementacao divergir do que foi especificado.
---

# Spec-driven development no PokeLab

Toda feature mora em `specs/NNN-nome-curto/` com tres arquivos. A ordem importa: nao se escreve `plan.md` antes da `spec.md` estar fechada, nem `tasks.md` antes do plano.

`NNN` e sequencial com tres digitos. `nome-curto` em kebab-case, em portugues, nomeando o que o professor ganha: `003-despacho-de-expedicao`, nao `003-expedition-service`.

## spec.md — o que e por que

Descreve **comportamento observavel**. Se um termo tecnico apareceu, voce escreveu no arquivo errado: endpoint, tabela, componente, biblioteca e nome de classe pertencem ao `plan.md`.

```markdown
# NNN — Titulo

## Problema
O que o professor nao consegue fazer hoje, e por que isso importa para o loop do jogo.

## Comportamento esperado
Narrativa do que passa a ser possivel. Escrita do ponto de vista de quem usa.

## Regras
Numeradas. Cada uma verificavel. Numeros concretos, nunca adjetivos.
1. Um treinador leva no maximo 3 Pokemon.
2. Um treinador em expedicao nao pode ter o time alterado.

## Criterios de aceite
Numerados, no formato dado-quando-entao. Cada um vira pelo menos um teste.
1. Dado um treinador com 3 Pokemon, quando o professor tentar adicionar um quarto, entao a operacao e rejeitada com mensagem explicando o limite.

## Fora de escopo
O que esta feature deliberadamente nao faz. Esta secao evita escopo acidental e e tao importante quanto as outras.

## Depende de
Fases ou specs que precisam estar prontas antes.
```

**Teste de qualidade da spec:** alguem que nunca viu o codigo consegue dizer se a implementacao esta certa lendo so os criterios de aceite? Se nao, a spec esta vaga.

## plan.md — como

Aqui entra a tecnologia.

```markdown
# NNN — Plano

## Abordagem
Dois ou tres paragrafos. A decisao central e por que ela, e nao a alternativa obvia.

## Contratos de API
Metodo, caminho, corpo de entrada, corpo de saida, codigos de erro.

## Modelo de dados
Tabelas e colunas novas ou alteradas, com a migracao prevista.

## Dominio
O que vai para api/app/game/, quais constantes entram em balance.py.

## Interface
Telas e componentes afetados.

## Riscos
O que pode dar errado e como a implementacao se protege.

## Fora deste plano
O que foi considerado e adiado, com o motivo.
```

## tasks.md — em que ordem

```markdown
# NNN — Tarefas

| # | Tarefa | Agente | Verificacao |
|---|---|---|---|
| 1 | Modelo e migracao de Expedicao | pokelab-api | `make migrate` aplica e reverte |
| 2 | Calculo de duracao em game/expedition.py | pokelab-domain | teste de tabela passa |
```

Cada tarefa e verificavel isoladamente e cabe numa sessao de trabalho. Se uma tarefa precisa de mais de um agente, ela sao duas tarefas.

## Quando a realidade diverge

Codigo que contraria a spec e um bug — da spec ou do codigo. Decidir qual e o primeiro passo da correcao, e isso e decisao do `pokelab-architect`.

A spec e atualizada no mesmo commit que muda o comportamento. Spec desatualizada e pior que spec ausente, porque mente com autoridade.
