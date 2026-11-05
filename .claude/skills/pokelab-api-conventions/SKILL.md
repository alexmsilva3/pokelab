---
name: pokelab-api-conventions
description: Convencoes da API do PokeLab — nomenclatura de rotas, envelope de erro, paginacao, codigos HTTP, autenticacao, escopo por laboratorio e padrao de migracao. Use em qualquer tarefa que toque api/app/routers, schemas, services ou repositories.
---

# Convencoes da API do PokeLab

## Camadas

```
routers/       traduz HTTP: valida entrada, chama o servico, formata a saida
services/      orquestra o caso de uso: transacao, relogio, seed, chamada ao dominio
repositories/  fala com o banco
game/          regra de jogo pura
schemas/       contrato de entrada e saida
models/        mapeamento SQLAlchemy
```

Nenhuma query dentro de um router. Nenhuma regra de jogo dentro de um servico. Nenhum import de infraestrutura dentro de `game/`.

## Rotas

Substantivo no plural, em ingles, kebab-case: `/expeditions`, `/trainers/{id}/team`.

Sub-recurso quando ha pertencimento real (`/trainers/{id}/team`); acao como verbo so quando nao e CRUD (`POST /expeditions/{id}/claim`).

Lista devolve envelope com paginacao:

```json
{ "items": [], "total": 0, "page": 1, "page_size": 20 }
```

## Codigos HTTP

| Codigo | Uso |
|---|---|
| 200 | leitura e atualizacao bem-sucedidas |
| 201 | criacao, com o recurso no corpo |
| 204 | exclusao |
| 400 | entrada malformada |
| 401 | sem token ou token invalido |
| 404 | nao existe **ou nao pertence ao laboratorio da sessao** |
| 409 | invariante de dominio violado (time cheio, expedicao ja em curso) |
| 422 | validacao de schema, gerado pelo FastAPI |

Recurso de outro professor devolve **404, nunca 403**. 403 confirma que o recurso existe.

## Erros

```json
{
  "erro": {
    "codigo": "TIME_CHEIO",
    "mensagem": "Este treinador ja leva 3 Pokemon.",
    "detalhes": { "limite": 3 }
  }
}
```

`codigo` em SCREAMING_SNAKE para a interface tratar. `mensagem` em portugues, dirigida ao professor, sem jargao tecnico. `detalhes` opcional e estruturado.

As excecoes de dominio de `game/` sao traduzidas para esse envelope por um handler unico em `main.py`. Um router nunca monta esse dicionario a mao.

## Schemas

Entrada e saida sao classes separadas: `ExpedicaoCriar` e `ExpedicaoLer`. Nunca devolva um modelo ORM.

Campo que o servidor deriva **nao existe** no schema de entrada (Artigo II). Se o cliente pode mandar a duracao, o cliente pode mentir a duracao.

Datas em ISO 8601 com timezone, sempre UTC. A interface converte para o fuso local.

## Autenticacao

JWT no header `Authorization: Bearer`. Uma dependencia `professor_atual` resolve o professor e o laboratorio, e toda rota autenticada a declara. Repositorio recebe `laboratorio_id` como parametro obrigatorio — nao como filtro opcional que alguem esquece de passar.

## Migracoes

Uma migracao por mudanca de modelo, com `downgrade` que funciona. Modelo novo importado em `alembic/env.py` para o autogenerate ve-lo. Nome do arquivo descreve a mudanca.

Migracao que apaga coluna com dado vai em duas etapas: parar de escrever, depois apagar.

## Idempotencia

Resolucao de expedicao, concessao de starters e coleta de recompensa: `SELECT ... FOR UPDATE` na linha, checagem de status na mesma transacao, teste de concorrencia obrigatorio (Artigo VII).
