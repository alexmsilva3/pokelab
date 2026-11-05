---
name: pokelab-domain-rules
description: Fonte unica das formulas, constantes e invariantes do PokeLab — experiencia, poder de time, dificuldade, duracao de expedicao, encontros e captura. Use em qualquer tarefa que toque regra de jogo, balanceamento ou validacao de dominio.
---

# Regras de dominio do PokeLab

As formulas vivem no codigo de `api/app/game/`. Os numeros vivem em `api/app/game/balance.py`. Esta skill e o contrato entre os dois — se o codigo divergir daqui, um dos dois esta errado.

A referencia completa e a secao 4 do `SDD.md`.

## Experiencia

```
exp_ganha = (experiencia_base_derrotado * nivel_derrotado / DIVISOR_EXP) / participantes
```

Experiencia acumulada para alcancar o nivel n, por curva de crescimento:

```
rapida        = 0.8  * n^3
media_rapida  =        n^3
media_lenta   = 1.2  * n^3 - 15 * n^2 + 100 * n - 140
lenta         = 1.25 * n^3
```

Evolucao dispara quando `nivel >= evolui_em_nivel` e a especie tem `evolui_para_id`. Na v1 so existe evolucao por nivel; pedra e troca estao fora de escopo.

Nivel maximo: 100.

## Poder e dificuldade

```
poder_pokemon = nivel * (1 + soma_stats_base / 600) * (hp_atual_pct / 100)
poder_time    = soma(poder_pokemon) * (1 + nivel_treinador * 0.03)

dificuldade   = nivel_selvagem_medio * nivel_dificuldade_local * FATOR_DIFICULDADE
razao         = poder_time / dificuldade

p_vitoria     = clamp(1 / (1 + e^(-2.5 * (razao - 1))), 0.05, 0.95)
```

A sigmoide existe para que nunca haja vitoria nem derrota garantida. Os limites de 5% e 95% sao inviolaveis: uma expedicao suicida ainda pode dar certo, e uma expedicao trivial ainda pode falhar.

## Duracao da expedicao

Dois tempos com significados diferentes: atravessar o caminho, e explorar o destino.

```
tempo_viagem     = soma de custo_travessia_minutos de cada local do caminho, exceto a origem
tempo_exploracao = encontros_base_destino * MINUTOS_POR_ENCONTRO

duracao = (tempo_viagem + tempo_exploracao)
        * (1 - min(nivel_treinador * 0.02, 0.40))
        * (1 - bonus_itens)
        / EXPEDITION_TIME_SCALE
```

O caminho e a menor rota no grafo de vizinhanca entre a origem da expedicao e o destino. A origem e o local desbloqueado de onde o treinador parte, nao necessariamente o laboratorio — e por isso que desbloquear encurta expedicoes de verdade.

`bonus_itens` limitado a 0.25. `EXPEDITION_TIME_SCALE` vem da configuracao (ADR-004) e e o unico valor desta skill que **nao** mora em `balance.py` — e ambiente, nao calibragem. O dominio recebe esse valor como parametro; nunca o le do ambiente (Artigo I).

## Encontros

```
qtd_encontros = max(1, encontros_base_destino + aleatorio(-1, +1))
```

A quantidade vem de `encontros_base` do destino, declarado no seed. **Nao derive a quantidade de encontros da duracao** — ritmo de sessao e rendimento sao decisoes separadas, e amarra-las foi um erro corrigido em 2026-11-05.

Especie sorteada pelo peso da tabela de encontros do local; nivel sorteado na faixa do local. Os pesos de um local somam 100, entao o peso le-se como porcentagem. A tabela legivel esta em `docs/encontros.md`, gerada por `tools/tabela_encontros.py`.

Vitoria: distribui EXP, pode disparar subida de nivel e evolucao, desgasta o time em 3 a 8 pontos de `hp_atual_pct`.

Derrota: consome uma Pocao ou Revive se houver, desgasta em 15 a 30 pontos. Tres derrotas sem item de cura encerram a expedicao em falha, com retorno antecipado e sem capturas.

## Captura

So apos vitoria, so com Pokebola na carga e slot disponivel.

```
slots_captura = min(pokebolas_na_carga, 1 + nivel_treinador // 5)

p_captura = clamp(
    (taxa_captura / 255)
  * multiplicador_bola
  * (1 + (nivel_time_medio - nivel_selvagem) * 0.02)
  * FATOR_CAPTURA,
  0.05, 0.90)
```

Multiplicadores: Poke Ball 1.0, Great Ball 1.5, Ultra Ball 2.0. A bola e consumida no sucesso e na falha.

## Os dez invariantes

1. Treinador tem no maximo 3 Pokemon.
2. Pokemon pertence a no maximo um treinador.
3. Treinador em expedicao nao tem time alterado nem e reenviado.
4. Pokemon de treinador em expedicao nao e desatribuido.
5. Laboratorio tem no maximo 2 expedicoes em curso na v1.
6. Destino deve ser vizinho de um local desbloqueado.
7. Nenhum Pokemon passa do nivel 100.
8. Expedicao e resolvida exatamente uma vez.
9. Estoque nunca fica negativo; carga e debitada no envio.
10. Starters sao concedidos uma unica vez por laboratorio.

Validados em `game/` com excecao propria e mensagem em portugues (Artigo VI). A constraint de banco e a segunda linha de defesa.

## Ao mudar qualquer coisa aqui

Mudanca de **numero** e calibragem: edite `balance.py`, nao edite esta skill, rode a simulacao.

Mudanca de **formula** ou de **invariante** e mudanca de regra: atualize a secao 4 do SDD, atualize esta skill, e so entao mude o codigo.
