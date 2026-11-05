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

TREINADORES_INICIAIS: Final[int] = 1
ESTOQUE_INICIAL: Final[dict[str, int]] = {
    "poke-ball": 10,
    "potion": 5,
    "revive": 1,
}

# --- Experiencia (SDD 4.1) -------------------------------------------------

# exp = (experiencia_base * nivel_derrotado / DIVISOR_EXP) / participantes
DIVISOR_EXP: Final[int] = 7
NIVEL_MAXIMO: Final[int] = 100

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

# --- Laboratorio -----------------------------------------------------------

SLOTS_EXPEDICAO_V1: Final[int] = 2
TAMANHO_MAXIMO_TIME: Final[int] = 3
