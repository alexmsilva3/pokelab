# 002 — Plano

## Abordagem

Autenticação por JWT de portador, com bcrypt para a senha. Sem sessão em banco, sem refresh token: a v1 não tem logout remoto nem revogação, e um token de validade curta com relogin manual resolve o problema real sem a máquina de estados que o resto traria.

A parte difícil desta fase não é a autenticação — é o **kit inicial**. Criar uma conta materializa, numa transação só, seis tipos de linha em cinco tabelas, e precisa ser atômico e idempotente (Artigo VII). É aí que mora o risco, e é aí que vão os testes.

## Modelo de dados

Entram seis tabelas de estado. Todas carregam `laboratorio_id` e são sempre consultadas por ele.

| Tabela | Chave | Observação |
|---|---|---|
| `professores` | `id` UUID | `usuario` único, comparado em minúsculas |
| `laboratorios` | `id` UUID | `professor_id` com **unique**, que é como o "um por conta" vira regra de banco |
| `pokemon_instancias` | `id` UUID | o indivíduo, distinto da espécie do seed |
| `treinadores` | `id` UUID | |
| `item_estoques` | `(laboratorio_id, item_id)` | chave composta; sem linha significa zero |
| `locais_desbloqueados` | `(laboratorio_id, local_id)` | |
| `pokedex_entradas` | `(laboratorio_id, especie_id)` | |

UUID e não inteiro sequencial nas entidades de estado: o id aparece em URL, e sequencial convida a enumerar o laboratório do vizinho. O 404-em-vez-de-403 da regra 12 protege de qualquer forma, mas não há motivo para facilitar a tentativa.

`laboratorios.professor_id` com constraint `UNIQUE` é o ponto onde a regra 5 fica impossível de violar, inclusive sob concorrência. Quando as regiões chegarem, remover a constraint é a migração inteira.

## Contratos de API

```
POST /auth/register   {usuario, senha, nome_exibicao?, nome_laboratorio?}
                      201 -> {token, professor, laboratorio}
                      409 -> USUARIO_EM_USO
                      422 -> senha curta demais

POST /auth/login      {usuario, senha}
                      200 -> {token, professor, laboratorio}
                      401 -> CREDENCIAIS_INVALIDAS (mesma resposta para
                             usuário inexistente e senha errada)

GET  /me              200 -> {professor, laboratorio, resumo}
                      401 -> sem token, token inválido ou expirado
```

`resumo` traz as contagens que o cabeçalho da tela precisa — Pokémon, treinadores, locais desbloqueados, espécies na Pokédex — para o laboratório não disparar quatro chamadas só para desenhar o topo.

Nenhum schema de saída contém `senha` ou `senha_hash`. Isso é garantido por teste, não por disciplina.

## Domínio

`game/kit_inicial.py` — função pura que recebe as espécies iniciais, as constantes de `balance.py` e um `random.Random` semeado, e devolve a **descrição** do que criar: quais Pokémon em que nível, o nome do treinador, as quantidades de cada item, o local a desbloquear. Não cria nada: devolve dados, e o serviço persiste. É o que mantém o Artigo I de pé.

`game/experience.py` — as quatro curvas de crescimento. Esta fase precisa delas para saber quanta experiência acumulada um starter de nível 5 tem. A Fase 7 depois só acrescenta o ganho por batalha e a distribuição entre o time. Antecipar aqui é mais honesto que chutar zero e corrigir depois.

`game/trainers.py` — geração de nome e avatar determinística a partir do gerador semeado. O avatar é iniciais mais uma cor derivada do id (questão 16), sem nenhum asset.

## Segurança

Hash bcrypt com custo padrão do passlib. Comparação de senha sempre executada, mesmo quando o usuário não existe, usando um hash descartável — senão o tempo de resposta denuncia quais usuários existem, e a regra 10 seria verdadeira só no texto.

`SECRET_KEY` vem do ambiente e o servidor recusa subir em produção com o valor de exemplo.

A dependência `professor_atual` resolve professor e laboratório de uma vez. Repositório recebe `laboratorio_id` como parâmetro obrigatório e posicional, nunca como filtro opcional que alguém esquece.

## Frontend

Token em `localStorage`. Uma store leve de autenticação, sem biblioteca de estado global — são três campos.

`RotaProtegida` redireciona para `/login` quando não há token. O cliente HTTP injeta o cabeçalho `Authorization` e, ao receber 401, limpa a sessão e manda para o login — assim um token expirado não vira uma tela quebrada.

A tela do laboratório deixa de ser o esqueleto da Fase 0 e passa a mostrar os dados reais do `/me`: nome do laboratório, nível, moedas, e as contagens do resumo.

## Riscos

| Risco | Mitigação |
|---|---|
| Kit concedido duas vezes em registros concorrentes | unique em `usuario` e em `professor_id`, tudo numa transação, teste de concorrência |
| Hash de senha vazando num schema de saída | schemas de saída separados e teste que varre toda resposta atrás de `senha` |
| Enumeração de usuários pelo tempo de resposta | hash falso comparado no caminho do usuário inexistente |
| Escopo esquecido num repositório novo | `laboratorio_id` posicional e obrigatório na assinatura |
| Migração grande quebrando no meio | uma migração só, transacional, com `downgrade` testado |

## Fora deste plano

Refresh token, revogação, rate limiting, recuperação de senha, OAuth. Paginação nas rotas desta fase — nenhuma devolve lista grande. Geração do cliente TypeScript a partir do OpenAPI: continua manual nesta fase, e vira tarefa quando a superfície da API justificar.
