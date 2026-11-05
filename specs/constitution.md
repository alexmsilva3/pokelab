# Constituição do PokeLab

Princípios invioláveis. Uma spec, um plano ou uma implementação que contrarie qualquer artigo abaixo está errada — e a correção começa aqui, não no código.

---

## Artigo I — O domínio é puro

Tudo em `api/app/game/` é Python puro e determinístico.

É **proibido** nesse diretório: importar SQLAlchemy, FastAPI, `requests`, `httpx`; ler `datetime.now()` ou `datetime.utcnow()`; usar `random` sem um gerador semeado recebido como parâmetro; ler variável de ambiente; tocar em arquivo.

O domínio recebe estado como argumento e devolve resultado. Quem busca e persiste esse estado é `services/` e `repositories/`. Essa fronteira é o que permite trocar a resolução de combate sem reescrever o jogo (ADR-003) e testar todas as regras sem subir infraestrutura.

## Artigo II — O servidor é a autoridade

Tempo, aleatoriedade e regra de jogo vivem no servidor. O cliente desenha o que a API devolve e nunca calcula resultado, duração restante ou probabilidade por conta própria.

Nenhum endpoint aceita do cliente um valor que o servidor possa derivar. Se o cliente pode mandar, o cliente pode mentir.

## Artigo III — Aleatoriedade é semeada e reproduzível

Toda rolagem deriva do `seed` gravado na expedição. Resolver a mesma expedição a partir do mesmo estado produz exatamente o mesmo relatório, sempre.

Um bug de balanceamento que não reproduz não é investigável, e uma simulação de tuning que não repete não vale nada.

## Artigo IV — Fórmula e constante são coisas diferentes

As fórmulas moram no código do domínio. Todo número que as alimenta mora em `api/app/game/balance.py`, com nome, unidade e comentário.

Calibragem altera `balance.py`. Nenhum número mágico literal em outro arquivo de `game/`.

## Artigo V — Os dados são um seed versionado

Espécies, locais, encontros e itens vêm de `data/seed/` e `data/sprites/`, versionados no repositório.

A aplicação em execução **nunca** chama a PokeAPI nem qualquer serviço externo. Atualizar dados é rodar o ingestor e commitar o diff — um ato deliberado, nunca efeito colateral de um deploy.

## Artigo VI — Invariantes são impostos no domínio

As regras da seção 3.3 do SDD são validadas em `game/`, não só no router nem só no banco. A constraint de banco é a segunda linha de defesa; a validação no router é conveniência de interface. A primeira linha é o domínio.

## Artigo VII — Escrita que muda estado é idempotente

Resolução de expedição, concessão de starters e coleta de recompensa executam uma única vez, sob lock, com checagem de status na mesma transação.

Toda operação dessa natureza tem um teste de concorrência. Não é opcional.

## Artigo VIII — A spec vem antes

Nenhuma feature começa sem `specs/NNN-nome/spec.md`. A spec descreve comportamento observável e critérios de aceite verificáveis; ela não menciona tabela, endpoint, biblioteca ou componente.

Decisão técnica é assunto do `plan.md`. Quando a realidade divergir da spec, atualiza-se a spec no mesmo commit.

## Artigo IX — O teste verifica a spec

O teste confere o critério de aceite, não o formato da implementação. Um teste que quebra quando o código é refatorado sem mudança de comportamento é um teste ruim.

Corrigir bug significa escrever primeiro o teste que falha.

## Artigo X — A linguagem do jogo é portuguesa

Interface, mensagens de erro, eventos do relatório de campo e documentação em português. Nomes próprios de Pokémon, locais e itens permanecem em inglês, como a comunidade usa.

Identificadores de código em inglês; nomes de domínio em português quando o conceito é nosso (`Expedicao`, `Treinador`, `Laboratorio`).

---

Alterar esta constituição exige registrar um ADR novo na seção 2 do SDD, dizendo qual artigo muda e por quê.
