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

**Treinador.** A cada batalha vencida leva um terco do que a batalha gerou, antes da divisao entre o time — a base e o total, para que o tamanho do time nao seja imposto sobre a carreira do treinador.

```
exp_treinador = (experiencia_base_derrotado * nivel_derrotado / DIVISOR_EXP) / 3
exp_total_para_nivel(n) = EXP_TREINADOR_BASE * n^2
```

**Laboratorio.** Cresce com o que o laboratorio produz, nao com o que acontece em campo.

```
expedicao bem-sucedida: EXP_LAB_POR_EXPEDICAO * (1 + nivel_dificuldade_local * 0.2)
entrega concluida:      EXP_LAB_POR_ENTREGA * total_entregue
exp_total_para_nivel(n) = EXP_LAB_BASE * n^2

limite_treinadores = TREINADORES_INICIAIS + (nivel_laboratorio - 1)
```

Nao existe limite fixo de expedicoes simultaneas. O gargalo e o numero de treinadores disponiveis, e portanto o nivel do laboratorio.

## Stats efetivos

O seed guarda o stat-base da especie. O que o individuo tem depende do nivel:

```
hp_efetivo   = floor(hp_base * MULTIPLICADOR_STAT * nivel / DIVISOR_STAT_NIVEL) + nivel + BONUS_HP_FIXO
stat_efetivo = floor(stat_base * MULTIPLICADOR_STAT * nivel / DIVISOR_STAT_NIVEL) + BONUS_STAT_FIXO
hp_atual     = 0  quando hp_atual_pct == 0 (nocauteado)
hp_atual     = min(hp_efetivo, max(HP_MINIMO_VIVO, round(hp_efetivo * hp_atual_pct / 100)))
```

O pct zero e tratado antes do piso: nocauteado e nocauteado, e mostrar 1 de HP mentiria sobre o estado. O piso existe para o problema oposto — um Pokemon a 2% de um HP alto nao pode aparecer como zero por arredondamento. Nocauteado nao e morto: ele se recupera no laboratorio (SDD 4.8).

Sem IV, EV nem natureza na v1: dois Pikachu de nivel 20 sao identicos. Quando houver engine de combate turno a turno (ADR-003), a individualidade entra junto.

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
        * EXPEDITION_TIME_SCALE
```

O caminho e a menor rota no grafo de vizinhanca entre a origem da expedicao e o destino. A origem e o local desbloqueado de onde o treinador parte, nao necessariamente o laboratorio — e por isso que desbloquear encurta expedicoes de verdade.

`bonus_itens` limitado a 0.25. `EXPEDITION_TIME_SCALE` MULTIPLICA (0.01 acelera cem vezes; dividir deixaria cem vezes mais lento) e vem da configuracao (ADR-004) e e o unico valor desta skill que **nao** mora em `balance.py` — e ambiente, nao calibragem. O dominio recebe esse valor como parametro; nunca o le do ambiente (Artigo I).

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
capacidade_bagagem = CAPACIDADE_TOTAL_TREINADOR - tamanho_do_time
slots_captura      = min(pokebolas_na_carga, capacidade_bagagem)

p_captura = clamp(
    (taxa_captura / 255)
  * multiplicador_bola
  * (1 + (nivel_time_medio - nivel_selvagem) * 0.02)
  * FATOR_CAPTURA,
  0.05, 0.90)
```

Multiplicadores: Poke Ball 1.0, Great Ball 1.5, Ultra Ball 2.0. A bola e consumida no sucesso e na falha.

Com `CAPACIDADE_TOTAL_TREINADOR = 6`, um treinador de time cheio traz ate 3 capturas e um de time unico traz ate 5. E trade-off deliberado: time grande vence mais encontros e captura menos. Atingida a capacidade, o treinador para de capturar mas **continua registrando** avistamentos na Pokedex.

## Entregas

Pedido gerado pelo jogo: levar Pokemon ate uma cidade desbloqueada. Ocupa um treinador, que entao nao vai a expedicao.

```
geracao:  1 a ESPECIES_MAXIMAS_POR_ENTREGA especies distintas, sorteadas do que o
          professor ja viu, peso PESO_ESPECIE_CAPTURADA para o capturado e
          PESO_ESPECIE_AVISTADA para o so avistado
duracao:  tempo_viagem(laboratorio, destino) * MULTIPLICADOR_IDA_E_VOLTA
          * (1 - min(nivel_treinador * 0.02, 0.40)) * EXPEDITION_TIME_SCALE
moedas:   soma por Pokemon de (MOEDA_BASE + nivel * MOEDA_POR_NIVEL)
          * (1 + tempo_viagem / MINUTOS_PARA_BONUS_DISTANCIA)
```

A entrega parte **sempre do laboratorio**, porque e la que os Pokemon estao — nao ha escolha de origem como na expedicao. Nao ha exploracao nem encontro: so estrada.

Os Pokemon entregues saem do laboratorio em definitivo. A interface confirma isso nominalmente antes do aceite.

A lista so e regerada a cada INTERVALO_REGERAR_ENTREGAS_MINUTOS. O intervalo existe para que escolher a entrega seja decisao, e nao um botao girado ate sair o pedido conveniente.

## Os dez invariantes

1. Treinador tem no maximo 3 Pokemon no time.
2. Pokemon pertence a no maximo um treinador.
3. Treinador ocupado (expedicao ou entrega) nao tem time alterado nem recebe nova missao.
4. Pokemon de treinador ocupado nao e desatribuido.
5. Laboratorio tem no maximo `limite_treinadores` treinadores.
6. Destino de expedicao deve ser vizinho de um local desbloqueado.
7. Nenhum Pokemon passa do nivel 100.
8. Expedicao ou entrega e resolvida exatamente uma vez.
9. Estoque nunca fica negativo; carga e debitada no envio.
10. Starters sao concedidos uma unica vez por laboratorio.
11. Treinador carrega no maximo CAPACIDADE_TOTAL_TREINADOR Pokemon (time + bagagem).
12. Entrega parte sempre do laboratorio.
13. Entrega pede no maximo ESPECIES_MAXIMAS_POR_ENTREGA especies distintas.
14. Pokemon comprometido com entrega nao entra em time, expedicao nem outra entrega.
15. Lista de entregas so e regerada apos o intervalo de espera.
16. Destino de entrega e sempre uma CIDADE ja desbloqueada.
17. Expedicao exige treinador com ao menos um Pokemon no time.

O invariante 17 nao e simetrico: treinador sem Pokemon e estado valido (e como os tres nascem), mas nao pode ser DESPACHADO em expedicao — sem time nao ha o que ganhar experiencia nem vencer encontro, e a expedicao voltaria em falha garantida tendo consumido tempo e itens. A regra vale so para expedicao: na entrega o treinador e mensageiro e carrega os Pokemon pedidos, que saem do laboratorio, entao time proprio nao faz diferenca.

Validados em `game/` com excecao propria e mensagem em portugues (Artigo VI). A constraint de banco e a segunda linha de defesa.

## Ao mudar qualquer coisa aqui

Mudanca de **numero** e calibragem: edite `balance.py`, nao edite esta skill, rode a simulacao.

Mudanca de **formula** ou de **invariante** e mudanca de regra: atualize a secao 4 do SDD, atualize esta skill, e so entao mude o codigo.
