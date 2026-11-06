# 003 — Plano

## Abordagem

Fase de leitura: nenhuma escrita além do apelido. O trabalho se divide em três frentes que quase não se tocam — consultas com filtro e paginação, um módulo de domínio para stats efetivos, e as telas.

O risco não é lógico, é de volume. `GET /pokemon` junta `pokemon_instancias` com `pokemon_especies` e pode filtrar por tipo, que mora na espécie. Feito ingenuamente, isso vira N+1: uma consulta para a página e uma por Pokémon para buscar a espécie. Tem que ser um join só, com `selectinload` ou `joinedload`, e um teste que conte as consultas emitidas.

## Domínio

`game/stats.py` — puro, sem I/O. Recebe os stats-base e o nível, devolve os efetivos pela fórmula da seção 4.2 do SDD. Constantes já estão em `balance.py`: `MULTIPLICADOR_STAT`, `DIVISOR_STAT_NIVEL`, `BONUS_STAT_FIXO`, `BONUS_HP_FIXO`, `HP_MINIMO_VIVO`.

Expõe também `hp_atual_absoluto(hp_efetivo, hp_atual_pct)`, porque a ficha mostra "38 / 45" e não uma porcentagem.

`game/experience.py` já tem `experiencia_para_o_proximo_nivel`, escrita na Fase 2 justamente prevendo esta tela. Use, não reimplemente.

## Contratos de API

```
GET /pokemon
    ?tipo=&nivel_min=&nivel_max=&atribuido=&page=&page_size=
    200 -> {items: [PokemonResumo], total, page, page_size}

GET /pokemon/{id}
    200 -> PokemonDetalhe   (stats efetivos, exp para o proximo nivel, origem, treinador)
    404 -> inexistente OU de outro laboratorio

PATCH /pokemon/{id}   {apelido: string | null}
    200 -> PokemonDetalhe
    404 -> idem

GET /pokedex
    200 -> {items: [EntradaPokedex x151], capturadas, vistas}

GET /items
    200 -> {items: [ItemEmEstoque]}   agrupavel por categoria no cliente
```

`tipo` aceita um dos dezoito tipos e casa com primário **ou** secundário. `atribuido` é um booleano de três estados: ausente não filtra, `true` traz só os que estão com treinador, `false` só os que estão no laboratório.

`page_size` tem teto de 100. Pedido acima disso é cortado em silêncio, não recusado — é limite de proteção, não regra de negócio.

### A Pokédex e o que ela não pode revelar

`EntradaPokedex` tem forma variável, de propósito:

```
desconhecida: {numero, estado: "DESCONHECIDA"}
vista:        {numero, estado: "VISTA", nome, tipos, sprite}
capturada:    {numero, estado: "CAPTURADA", nome, tipos, sprite, quantidade}
```

O nome de uma espécie nunca vista **não vai no corpo da resposta**. Mandar os 151 nomes e esconder no CSS é vazamento: basta abrir o devtools. O critério de aceite 9 cobre isso.

## Sprites

`StaticFiles` montado em `/sprites`, servindo `data/sprites/`, com `Cache-Control: public, max-age=31536000, immutable`. Os arquivos são seed versionado e nunca mudam sob o mesmo nome, então cache eterno é correto e não precisa de hash no caminho.

A API serve, não o nginx do frontend: em desenvolvimento são hosts diferentes, e deixar o dono dos dados servir os dados evita configurar CORS de imagem e duplicar o volume em dois serviços. Se virar gargalo, é uma linha de nginx depois.

Os schemas devolvem o caminho relativo (`25-front.png`), e o cliente monta a URL com a base da API. Caminho absoluto no banco amarraria o acervo ao host.

## Frontend

```
pages/Laboratorio.tsx     cabecalho + lista paginada + filtros
pages/Pokedex.tsx         grade de 151
components/ListaPokemon.tsx
components/CartaoPokemon.tsx
components/FichaPokemon.tsx   painel lateral de detalhe
components/FiltrosPokemon.tsx
components/Mochila.tsx
components/SpritePokemon.tsx  img + silhueta + alt correto
api/pokemon.ts, api/pokedex.ts, api/itens.ts
```

A ficha é painel lateral, não rota própria: o professor compara Pokémon de uma lista, e perder a lista a cada clique atrapalha exatamente o que ele está tentando fazer.

A silhueta é `filter: brightness(0)` sobre o sprite — mas só é aplicada a espécies **vistas** cuja imagem o servidor mandou. Para desconhecida não há sprite nenhum: o espaço mostra o número e um contorno neutro.

Estado de filtro na URL, via query string. Recarregar a página mantendo o filtro é o comportamento esperado de uma lista, e dá link compartilhável de graça.

## Riscos

| Risco | Mitigação |
|---|---|
| N+1 ao listar Pokémon com a espécie | join único; teste que conta consultas emitidas |
| Nome de espécie desconhecida vazando no JSON | forma variável do schema; teste que varre a resposta |
| Pokédex de 151 itens pesada a cada abertura | resposta é pequena (número, nome curto, dois tipos); medir antes de otimizar |
| Filtro de tipo esquecendo o secundário | teste com espécie de dois tipos filtrada pelo segundo |
| Escopo esquecido numa rota nova | `laboratorio_id` posicional e obrigatório; teste de 404 cruzado |

## Fora deste plano

Cache de resposta, índice de texto, virtualização da lista, lazy loading de imagem por observador de interseção. A v1 tem no máximo algumas centenas de Pokémon por laboratório e 151 slots de Pokédex; otimizar isso agora é inventar um problema.
