"""Constantes de calibragem do PokeLab.

Artigo IV da constituicao: as formulas moram nos modulos de game/, todo numero que
as alimenta mora aqui, com nome, unidade e motivo. Nenhum literal magico em
qualquer outro arquivo de game/.

Os valores abaixo sao o ponto de partida da secao 4 do SDD e serao calibrados por
simulacao na Fase 8. Alterar um numero daqui nao e mudanca de regra.
"""

from typing import Final

# --- Kit inicial (Fase 2) --------------------------------------------------

STARTER_SPECIES_IDS: Final[tuple[int, int, int]] = (1, 4, 7)  # Bulbasaur, Charmander, Squirtle
STARTER_LEVEL: Final[int] = 5
LOCAL_INICIAL_ID: Final[str] = "pallet-town"

# Dois numeros distintos que ja foram confundidos por terem nome parecido:
# quantos treinadores o kit CONCEDE, e quantos o laboratorio COMPORTA.
# Tres treinadores para tres iniciais: o professor distribui como quiser desde
# o primeiro minuto, e a escolha de quem leva quem ja e decisao de jogo. Na v1
# nao ha recrutamento, entao este numero tambem e o total que existira.
TREINADORES_NO_KIT_INICIAL: Final[int] = 3
ESTOQUE_INICIAL: Final[dict[str, int]] = {
    "poke-ball": 10,
    "potion": 5,
    "revive": 1,
}

# --- Experiencia (SDD 4.1) -------------------------------------------------

# exp = (experiencia_base * nivel_derrotado / DIVISOR_EXP) / participantes
DIVISOR_EXP: Final[int] = 7
NIVEL_MAXIMO: Final[int] = 100

# Experiencia do treinador: um terco do que a batalha gerou, antes da divisao
# entre o time. A base e o total para que o tamanho do time nao vire imposto
# sobre a carreira do treinador.
FRACAO_EXP_TREINADOR: Final[float] = 1 / 3
EXP_TREINADOR_BASE: Final[int] = 60  # exp total para o nivel n = base * n^2

# Experiencia do laboratorio: cresce com o que o laboratorio produz.
EXP_LAB_BASE: Final[int] = 500  # exp total para o nivel n = base * n^2
EXP_LAB_POR_EXPEDICAO: Final[int] = 100
BONUS_EXP_LAB_POR_DIFICULDADE: Final[float] = 0.2  # +20% por ponto de dificuldade
EXP_LAB_POR_ENTREGA: Final[int] = 80  # por Pokemon entregue

# Multiplicadores das curvas de crescimento, aplicados sobre n^3.
CURVA_RAPIDA: Final[float] = 0.8
CURVA_MEDIA_RAPIDA: Final[float] = 1.0
CURVA_LENTA: Final[float] = 1.25
# media_lenta usa polinomio proprio: 1.2n^3 - 15n^2 + 100n - 140
CURVA_MEDIA_LENTA_A: Final[float] = 1.2
CURVA_MEDIA_LENTA_B: Final[float] = 15.0
CURVA_MEDIA_LENTA_C: Final[float] = 100.0
CURVA_MEDIA_LENTA_D: Final[float] = 140.0

# --- Evolucao (SDD 4.1) ----------------------------------------------------

# Teto de evolucoes encadeadas que uma unica aplicacao de experiencia pode
# disparar, em etapas. Nao e regra de jogo: e guarda contra dado circular no
# seed, onde `evolui_para_id` apontasse de volta para um elo anterior e o laco
# girasse para sempre dentro de uma requisicao. A maior linha evolutiva de
# Kanto tem duas etapas (Bulbasaur -> Ivysaur -> Venusaur, e um salto do nivel
# 15 ao 33 numa expedicao longa dispara as duas), e a terceira e folga para um
# seed futuro. Atingir o teto significa seed invalido, e o dominio levanta.
EVOLUCOES_MAXIMAS_POR_EXPEDICAO: Final[int] = 3

# --- Avatar de treinador (questao 16) --------------------------------------

# O avatar nao e arquivo: e iniciais mais uma cor, derivadas da semente. O
# digest precisa ser estavel entre processos, dai blake2b em vez de hash().
BYTES_DIGEST_AVATAR: Final[int] = 8  # bytes do digest usados para sortear a cor
LETRAS_INICIAIS_AVATAR: Final[int] = 2  # quantas letras o circulo do avatar mostra

# --- Stats efetivos (SDD 4.2) ----------------------------------------------

# Formula das geracoes modernas sem IV, EV nem natureza: a v1 nao tem
# individualidade dentro da especie. HP tem bonus proprio para que nivel baixo
# nao morra de um golpe.
MULTIPLICADOR_STAT: Final[int] = 2
DIVISOR_STAT_NIVEL: Final[int] = 100
BONUS_STAT_FIXO: Final[int] = 5
BONUS_HP_FIXO: Final[int] = 10
HP_MINIMO_VIVO: Final[int] = 1

# hp_atual_pct e guardado em porcento (0..100), e nao como fracao: e o que a
# coluna hp_atual_pct grava e o que o desgaste da expedicao soma e subtrai.
BASE_PERCENTUAL: Final[int] = 100

# --- Poder e dificuldade (SDD 4.3) -----------------------------------------

SOMA_STATS_BASE_REFERENCIA: Final[int] = 600  # normalizador do bonus de stats

# O poder sai com uma casa decimal, nao inteiro. Com time pequeno e nivel baixo
# o passo de 3% por nivel de treinador cabe inteiro dentro do arredondamento:
# um Bulbasaur nivel 5 com treinador de nivel 1, 2 ou 3 dava 8 nos tres casos,
# tornando falso o criterio de aceite 9 da spec 004. Casa decimal preserva a
# diferenca sem mexer na razao poder/dificuldade de que a Fase 7 depende.
CASAS_DECIMAIS_PODER: Final[int] = 1
BONUS_POR_NIVEL_TREINADOR: Final[float] = 0.03  # +3% de poder por nivel
FATOR_DIFICULDADE: Final[float] = 1.0  # escala global, alvo da Fase 8

# A dificuldade sai com a mesma precisao do poder porque os dois sao gravados
# lado a lado na expedicao e divididos um pelo outro: a razao recalculada a
# partir das colunas precisa dar exatamente a chance que o professor viu.
CASAS_DECIMAIS_DIFICULDADE: Final[int] = 1

INCLINACAO_SIGMOIDE: Final[float] = 2.5
P_VITORIA_MINIMA: Final[float] = 0.05
P_VITORIA_MAXIMA: Final[float] = 0.95

# Quatro casas na probabilidade: a tela mostra porcentagem com uma decimal, e
# duas casas a mais evitam que o arredondamento da exibicao decida o resultado.
CASAS_DECIMAIS_CHANCE: Final[int] = 4

# Abaixo de -709 o exp() de ponto flutuante duplo ja devolve zero, e converter
# o expoente para float estouraria. Nao e calibragem: e o limite do double, e
# so existe para que uma razao absurda sature no teto em vez de levantar.
EXPOENTE_LIMITE_SIGMOIDE: Final[float] = 709.0

# --- Duracao da expedicao (SDD 4.3) ----------------------------------------

# A duracao e a soma de dois tempos com significados diferentes: atravessar o
# caminho ate o destino, e explorar o destino. Cada local traz o proprio
# custo_travessia_minutos e o proprio encontros_base no seed.
MINUTOS_POR_ENCONTRO: Final[int] = 3  # tempo de exploracao que cada encontro custa

REDUCAO_POR_NIVEL_TREINADOR: Final[float] = 0.02  # -2% de duracao por nivel
REDUCAO_MAXIMA_TREINADOR: Final[float] = 0.40
BONUS_ITENS_MAXIMO: Final[float] = 0.25

# Piso da duracao, em minutos. Com a escala de tempo acelerada do ADR-004 a
# conta chega a valores abaixo de um minuto, e uma expedicao de zero minuto
# terminaria no mesmo instante em que parte: nao ha ida nem relatorio.
DURACAO_MINIMA_MINUTOS: Final[int] = 1

# Maior semente aceita no despacho (ADR-005). E a largura do inteiro que a
# coluna guarda: uma semente maior que isto seria truncada na gravacao, e
# truncar semente quebra o Artigo III sem dar sinal nenhum.
SEED_MAXIMO: Final[int] = 2**63 - 1

# --- Encontros (SDD 4.4) ---------------------------------------------------

# A quantidade de encontros vem de encontros_base do destino, nao da duracao:
# ritmo da sessao e rendimento da expedicao sao decisoes de design separadas.
VARIACAO_ENCONTROS: Final[int] = 1
ENCONTROS_MINIMOS: Final[int] = 1

DESGASTE_VITORIA: Final[tuple[int, int]] = (3, 8)  # pontos de hp_atual_pct
DESGASTE_DERROTA: Final[tuple[int, int]] = (15, 30)
DERROTAS_PARA_FALHAR: Final[int] = 3

# --- Recuperacao passiva (SDD 4.8) -----------------------------------------

# Minutos de jogo que valem um ponto de hp_atual_pct enquanto o Pokemon esta
# no laboratorio. A conta que fixa o numero:
#
#   uma expedicao tira de 15 a 40 pontos (3 a 8 por vitoria, 15 a 30 por
#   derrota). Com 2 minutos por ponto, esse estrago volta em 30 a 80 minutos,
#   que e da mesma ordem de grandeza de uma expedicao (Pallet leva 15 min,
#   Mt. Moon partindo de Pallet leva 55). O professor sente a espera e tem
#   motivo para girar os tres treinadores, sem que o jogo trave.
#
#   do zero ao cheio: 100 pontos * 2 = 200 minutos, 3h20 de tempo real.
#   Com EXPEDITION_TIME_SCALE = 0.01 em desenvolvimento, o servico alimenta
#   esta funcao com 100x os minutos de relogio, e os mesmos 200 minutos de
#   jogo passam em 2 minutos reais.
#
# A conversao de relogio para minutos de jogo e do servico: a escala de tempo
# e ambiente, nao calibragem, e o Artigo I proibe le-la aqui dentro.
MINUTOS_POR_PONTO_DE_HP: Final[int] = 2

# --- Captura (SDD 4.5) -----------------------------------------------------

TAXA_CAPTURA_MAXIMA: Final[int] = 255
# NIVEIS_POR_SLOT_CAPTURA saiu daqui na Fase 7. Ela vinha de uma regra antiga
# ("slots = 1 + nivel_treinador // 5") que o SDD 4.6 substituiu por
# `min(pokebolas_na_carga, CAPACIDADE_TOTAL_TREINADOR - tamanho_do_time)`.
# Nenhum modulo a lia, e constante orfa em balance.py e armadilha de
# calibragem: a Fase 9 mexeria num numero que nao alimenta formula nenhuma.
BONUS_CAPTURA_POR_NIVEL: Final[float] = 0.02
FATOR_CAPTURA: Final[float] = 1.0  # escala global, alvo da Fase 8
P_CAPTURA_MINIMA: Final[float] = 0.05
P_CAPTURA_MAXIMA: Final[float] = 0.90

# NAO e a fonte do multiplicador em campo. A resolucao usa `Item.potencia` do
# seed (SDD 3.1), que e de onde a carga da expedicao ja vem: ler as duas
# fontes abriria a chance de elas discordarem, e a que vale no jogo seria a do
# banco. Este dicionario fica como o valor ESPERADO do seed, conferido por
# `test_seed_integridade.py`, para que um ingestor que mudasse a potencia de
# uma Pokebola sem querer quebrasse um teste em vez de mover a economia em
# silencio. Calibrar a captura e mexer em FATOR_CAPTURA, nao aqui.
MULTIPLICADOR_BOLA: Final[dict[str, float]] = {
    "poke-ball": 1.0,
    "great-ball": 1.5,
    "ultra-ball": 2.0,
}

# --- Achados de item em campo (tarefa 7.12 do SDD) -------------------------

# A regra existe para que uma expedicao se pague PARCIALMENTE em Pokebolas,
# sem tornar irrelevante a loja da Fase 8. A conta que fixa os numeros:
#
#   consumo  — cada tentativa de captura gasta uma bola, e o numero de
#              tentativas e limitado por slots_de_captura (3 a 5). Uma
#              expedicao tipica de 5 encontros com 70% de vitoria gasta
#              de 3 a 4 bolas.
#   retorno  — bolas_por_vitoria = CHANCE_ITEM_POR_VITORIA
#                                * peso_das_bolas / peso_total
#                                * quantidade
#              = 0,25 * 0,80 * 1 = 0,20 por vitoria num local de dificuldade
#              baixa, e 0,25 * 0,80 * 2 = 0,40 em Mt. Moon (dificuldade 5).
#
# Com 3,5 vitorias por expedicao isso devolve de 0,7 a 1,4 bola contra 3 a 4
# gastas: a expedicao paga de 20% a 35% da propria mochila. Qualquer numero
# que passasse de 1,0 bola por vitoria faria a expedicao se financiar sozinha
# e a economia da Fase 8 nasceria morta.
CHANCE_ITEM_POR_VITORIA: Final[float] = 0.25

# Pesos relativos do sorteio do achado. Somam 100 de proposito, para que o
# peso se leia como porcentagem: Pokebola comum (80%), cura rara (20%).
# A ordem e canonica e importa para o Artigo III — o sorteio acumula os pesos
# na ordem desta tupla, e reordenar muda o resultado de toda semente gravada.
TABELA_DE_ACHADOS: Final[tuple[tuple[str, int], ...]] = (
    ("poke-ball", 65),
    ("great-ball", 15),
    ("potion", 15),
    ("revive", 5),
)

# Pontos de nivel_dificuldade do local por unidade extra no achado:
# quantidade = 1 + (nivel_dificuldade // DIFICULDADE_POR_ITEM_EXTRA).
# Com 4, a faixa 1..3 do mapa inicial da 1, Mt. Moon (5) da 2 e so os locais
# de dificuldade 8 a 10 dao 3. O lugar mais perigoso paga melhor sem que o
# rendimento triplique logo na segunda rota.
DIFICULDADE_POR_ITEM_EXTRA: Final[int] = 4

# --- Relatorio de campo (spec 007) -----------------------------------------

# Caracteres que o texto de um evento do relatorio pode ter. Nao e calibragem:
# e a largura da coluna que guarda o texto, declarada aqui porque o Artigo IV
# nao abre excecao para numero nenhum fora deste arquivo. Mesma natureza de
# SEED_MAXIMO e de EXPOENTE_LIMITE_SIGMOIDE. A frase mais longa que as
# variantes de `narrativa.py` produzem fica perto de 120 caracteres, e a folga
# existe para nome de local e de item que ainda nao estao no seed.
LIMITE_TEXTO_DO_EVENTO: Final[int] = 500

# --- Treinador e laboratorio -----------------------------------------------

TAMANHO_MAXIMO_TIME: Final[int] = 3
# Time mais bagagem. O que sobra do time e quanto o treinador consegue capturar:
# time grande vence mais e captura menos, time pequeno faz o contrario.
CAPACIDADE_TOTAL_TREINADOR: Final[int] = 6

# Nao ha limite fixo de expedicoes simultaneas: o gargalo sao os treinadores
# disponiveis, e portanto o nivel do laboratorio.
LIMITE_TREINADORES_NIVEL_1: Final[int] = 3
TREINADORES_POR_NIVEL_LABORATORIO: Final[int] = 1  # acrescidos a cada nivel

# --- Entregas (SDD 4.8) ----------------------------------------------------

ENTREGAS_DISPONIVEIS: Final[int] = 3  # pedidos na lista ao mesmo tempo
ESPECIES_MAXIMAS_POR_ENTREGA: Final[int] = 3
QUANTIDADE_MAXIMA_POR_ESPECIE: Final[int] = 3

# O teto de quantidade de cada especie e ponderado pela taxa de captura, para
# que o gerador nao peca tres Dragonite. taxa 255 -> 3, 190 -> 2, 120 ou menos
# -> 1. Sem isso o pedido raro nasce morto e so queima um slot da lista.
DIVISOR_QUANTIDADE_POR_CAPTURA: Final[int] = 85
INTERVALO_REGERAR_ENTREGAS_MINUTOS: Final[int] = 15

# Peso relativo no sorteio: especie ja capturada aparece mais que a so avistada,
# para a lista ter pedidos atendiveis hoje e alguns que valem como objetivo.
PESO_ESPECIE_CAPTURADA: Final[int] = 4
PESO_ESPECIE_AVISTADA: Final[int] = 1

MULTIPLICADOR_IDA_E_VOLTA: Final[float] = 2.0

MOEDA_BASE: Final[int] = 25  # por Pokemon entregue
MOEDA_POR_NIVEL: Final[int] = 5
MINUTOS_PARA_BONUS_DISTANCIA: Final[int] = 30  # bonus = 1 + viagem / este valor
EXP_TREINADOR_POR_ENTREGA: Final[int] = 150
