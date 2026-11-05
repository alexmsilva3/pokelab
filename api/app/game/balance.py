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

TREINADORES_INICIAIS: Final[int] = 1  # concedido no registro
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

# --- Poder e dificuldade (SDD 4.2) -----------------------------------------

SOMA_STATS_BASE_REFERENCIA: Final[int] = 600  # normalizador do bonus de stats
BONUS_POR_NIVEL_TREINADOR: Final[float] = 0.03  # +3% de poder por nivel
FATOR_DIFICULDADE: Final[float] = 1.0  # escala global, alvo da Fase 8

INCLINACAO_SIGMOIDE: Final[float] = 2.5
P_VITORIA_MINIMA: Final[float] = 0.05
P_VITORIA_MAXIMA: Final[float] = 0.95

# --- Duracao da expedicao (SDD 4.3) ----------------------------------------

# A duracao e a soma de dois tempos com significados diferentes: atravessar o
# caminho ate o destino, e explorar o destino. Cada local traz o proprio
# custo_travessia_minutos e o proprio encontros_base no seed.
MINUTOS_POR_ENCONTRO: Final[int] = 3  # tempo de exploracao que cada encontro custa

REDUCAO_POR_NIVEL_TREINADOR: Final[float] = 0.02  # -2% de duracao por nivel
REDUCAO_MAXIMA_TREINADOR: Final[float] = 0.40
BONUS_ITENS_MAXIMO: Final[float] = 0.25

# --- Encontros (SDD 4.4) ---------------------------------------------------

# A quantidade de encontros vem de encontros_base do destino, nao da duracao:
# ritmo da sessao e rendimento da expedicao sao decisoes de design separadas.
VARIACAO_ENCONTROS: Final[int] = 1
ENCONTROS_MINIMOS: Final[int] = 1

DESGASTE_VITORIA: Final[tuple[int, int]] = (3, 8)  # pontos de hp_atual_pct
DESGASTE_DERROTA: Final[tuple[int, int]] = (15, 30)
DERROTAS_PARA_FALHAR: Final[int] = 3

# --- Captura (SDD 4.5) -----------------------------------------------------

TAXA_CAPTURA_MAXIMA: Final[int] = 255
NIVEIS_POR_SLOT_CAPTURA: Final[int] = 5  # slots = 1 + nivel_treinador // 5
BONUS_CAPTURA_POR_NIVEL: Final[float] = 0.02
FATOR_CAPTURA: Final[float] = 1.0  # escala global, alvo da Fase 8
P_CAPTURA_MINIMA: Final[float] = 0.05
P_CAPTURA_MAXIMA: Final[float] = 0.90

MULTIPLICADOR_BOLA: Final[dict[str, float]] = {
    "poke-ball": 1.0,
    "great-ball": 1.5,
    "ultra-ball": 2.0,
}

# --- Treinador e laboratorio -----------------------------------------------

TAMANHO_MAXIMO_TIME: Final[int] = 3
# Time mais bagagem. O que sobra do time e quanto o treinador consegue capturar:
# time grande vence mais e captura menos, time pequeno faz o contrario.
CAPACIDADE_TOTAL_TREINADOR: Final[int] = 6

# Nao ha limite fixo de expedicoes simultaneas: o gargalo sao os treinadores
# disponiveis, e portanto o nivel do laboratorio.
TREINADORES_POR_NIVEL_LABORATORIO: Final[int] = 1  # alem dos TREINADORES_INICIAIS

# --- Entregas (SDD 4.8) ----------------------------------------------------

ENTREGAS_DISPONIVEIS: Final[int] = 3  # pedidos na lista ao mesmo tempo
ESPECIES_MAXIMAS_POR_ENTREGA: Final[int] = 3
QUANTIDADE_MAXIMA_POR_ESPECIE: Final[int] = 3
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
