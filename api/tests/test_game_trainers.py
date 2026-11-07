"""Treinador: nome, avatar (questao 16) e progressao de nivel (SDD 4.1).

O ponto sensivel aqui e o Artigo III. Nome, avatar e curva precisam ser os
mesmos em qualquer processo, em qualquer maquina, hoje e depois do proximo
deploy.
"""

import random
import re
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.game import balance
from app.game.erros import AvatarInvalido, ErroDeDominio, ExperienciaInvalida
from app.game.trainers import (
    CLASSES_DE_TREINADOR,
    NOMES_DE_TREINADOR,
    PALETA_AVATAR,
    Avatar,
    NivelDeTreinadorInvalido,
    StatusTreinador,
    exigir_nivel_de_treinador,
    experiencia_ganha_por_batalha,
    experiencia_para_o_proximo_nivel,
    experiencia_total_para_nivel,
    gerar_avatar,
    gerar_nome,
    gerar_treinador,
    nivel_para_experiencia,
    status_de,
)

RAIZ_API = Path(__file__).resolve().parent.parent


def test_ha_nomes_suficientes_e_sem_repeticao():
    assert len(NOMES_DE_TREINADOR) >= 40
    assert len(set(NOMES_DE_TREINADOR)) == len(NOMES_DE_TREINADOR)


def test_nome_sorteado_sai_da_lista():
    for semente in range(200):
        assert gerar_nome(random.Random(semente)) in NOMES_DE_TREINADOR


def test_mesmo_seed_produz_o_mesmo_nome():
    primeira = [gerar_nome(random.Random(7)) for _ in range(5)]
    assert primeira == [gerar_nome(random.Random(7)) for _ in range(5)]


def test_mesmo_gerador_em_sequencia_e_reproduzivel():
    rng_a = random.Random(1234)
    rng_b = random.Random(1234)
    assert [gerar_nome(rng_a) for _ in range(10)] == [gerar_nome(rng_b) for _ in range(10)]


def test_seeds_diferentes_produzem_nomes_diferentes_na_amostra():
    nomes = {gerar_nome(random.Random(semente)) for semente in range(100)}
    assert len(nomes) > 1


def test_avatar_tem_iniciais_e_cor_da_paleta():
    avatar = gerar_avatar("Ariel")
    assert avatar.iniciais == "AR"
    assert avatar.cor in PALETA_AVATAR
    assert re.fullmatch(r"#[0-9a-f]{6}", avatar.cor)


def test_avatar_de_nome_composto_usa_primeira_e_ultima_inicial():
    assert gerar_avatar("Ana Beatriz").iniciais == "AB"
    assert gerar_avatar("Joao Pedro Silva").iniciais == "JS"


def test_avatar_e_serializavel():
    avatar = gerar_avatar("Kai")
    assert avatar.para_dicionario() == {
        "iniciais": "KA",
        "cor": avatar.cor,
        "classe": avatar.classe,
    }


def test_avatar_e_imutavel():
    avatar = gerar_avatar("Milo")
    with pytest.raises(FrozenInstanceError):
        avatar.iniciais = "XX"  # type: ignore[misc]


def test_mesma_semente_produz_o_mesmo_avatar():
    assert gerar_avatar("Quinn") == gerar_avatar("Quinn")


def test_sementes_diferentes_espalham_pela_paleta():
    cores = {gerar_avatar(nome).cor for nome in NOMES_DE_TREINADOR}
    assert len(cores) > 1


def test_semente_vazia_e_recusada():
    with pytest.raises(AvatarInvalido, match="vazia"):
        gerar_avatar("   ")


def test_semente_sem_letra_e_recusada():
    with pytest.raises(AvatarInvalido, match="letra"):
        gerar_avatar("12 34")


def test_treinador_gerado_combina_nome_e_avatar():
    treinador = gerar_treinador(random.Random(99))
    assert treinador.nome in NOMES_DE_TREINADOR
    assert treinador.avatar == gerar_avatar(treinador.nome)
    assert gerar_treinador(random.Random(99)) == treinador


def test_cor_do_avatar_e_estavel_entre_processos():
    """Se a cor viesse de hash(), este teste falharia: ele troca o PYTHONHASHSEED."""
    programa = (
        "from app.game.trainers import gerar_avatar;"
        "print(gerar_avatar('Ariel').cor, gerar_avatar('Zuri').cor)"
    )
    resultados = []
    for semente_do_processo in ("0", "1", "random"):
        saida = subprocess.run(
            [sys.executable, "-c", programa],
            cwd=RAIZ_API,
            capture_output=True,
            text=True,
            check=True,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin", "PYTHONHASHSEED": semente_do_processo},
        )
        resultados.append(saida.stdout.strip())
    assert len(set(resultados)) == 1
    esperado = f"{gerar_avatar('Ariel').cor} {gerar_avatar('Zuri').cor}"
    assert resultados[0] == esperado


def test_avatar_declarado_diretamente_mantem_o_contrato():
    assert Avatar(iniciais="AB", cor="#1f7a3f", classe="youngster").para_dicionario() == {
        "iniciais": "AB",
        "cor": "#1f7a3f",
        "classe": "youngster",
    }


def test_a_classe_sai_do_catalogo_e_e_estavel():
    for nome in ("Kai", "Milo", "Pat", "Jordan", "Yuki"):
        avatar = gerar_avatar(nome)
        assert avatar.classe in CLASSES_DE_TREINADOR
        assert gerar_avatar(nome).classe == avatar.classe


def test_o_sprite_aponta_para_o_acervo_de_treinadores():
    assert gerar_avatar("Kai").sprite == f"treinadores/{gerar_avatar('Kai').classe}.png"


def test_cor_e_classe_nao_andam_juntas():
    # Saem do mesmo digest, de fatias diferentes: se andassem juntas, todo
    # treinador de uma cor teria sempre o mesmo retrato.
    pares = {(gerar_avatar(n).cor, gerar_avatar(n).classe) for n in NOMES_DE_TREINADOR}
    cores = {cor for cor, _ in pares}
    assert len(pares) > len(cores)


# --- Status (SDD 3.2 e invariante 3) ----------------------------------------


@pytest.mark.parametrize(
    ("status", "ocupado"),
    [
        (StatusTreinador.DISPONIVEL, False),
        (StatusTreinador.EM_EXPEDICAO, True),
        (StatusTreinador.EM_ENTREGA, True),
        (StatusTreinador.DESCANSANDO, False),
    ],
)
def test_so_expedicao_e_entrega_ocupam_o_treinador(status, ocupado):
    assert status.ocupado is ocupado


def test_status_e_lido_do_texto_gravado_na_coluna():
    assert status_de("EM_EXPEDICAO") is StatusTreinador.EM_EXPEDICAO


def test_status_desconhecido_e_recusado():
    with pytest.raises(ErroDeDominio, match="desconhecido"):
        status_de("DE_FERIAS")


# --- Curva de nivel (SDD 4.1) -----------------------------------------------


def test_treinador_nasce_sem_experiencia():
    # Nivel 1 custa zero: um treinador recem-chegado nao nasce devendo.
    assert experiencia_total_para_nivel(1) == 0


@pytest.mark.parametrize(
    ("nivel", "esperado"),
    [
        # EXP_TREINADOR_BASE * (n - 1)^2, com EXP_TREINADOR_BASE = 60.
        (1, 0),
        (2, 60),
        (3, 240),
        (4, 540),
        (5, 960),
        (10, 4860),
    ],
)
def test_tabela_da_curva_do_treinador(nivel, esperado):
    assert experiencia_total_para_nivel(nivel) == esperado


def test_curva_usa_a_constante_de_balance():
    assert experiencia_total_para_nivel(2) == balance.EXP_TREINADOR_BASE


def test_a_curva_do_treinador_e_quadratica():
    # Quadratica, nao cubica como a de um Pokemon: dobrar a distancia ate o
    # nivel 1 quadruplica o custo, em vez de multiplica-lo por oito.
    for nivel in range(2, 51):
        dobro = 2 * nivel - 1
        assert experiencia_total_para_nivel(dobro) == 4 * experiencia_total_para_nivel(nivel)


def test_experiencia_e_nivel_sao_inversos():
    for nivel in range(1, balance.NIVEL_MAXIMO + 1):
        assert nivel_para_experiencia(experiencia_total_para_nivel(nivel)) == nivel


def test_experiencia_logo_abaixo_do_corte_nao_sobe_de_nivel():
    for nivel in range(2, balance.NIVEL_MAXIMO + 1):
        assert nivel_para_experiencia(experiencia_total_para_nivel(nivel) - 1) == nivel - 1


def test_nivel_nunca_passa_do_maximo():
    muito = experiencia_total_para_nivel(balance.NIVEL_MAXIMO) * 1000
    assert nivel_para_experiencia(muito) == balance.NIVEL_MAXIMO


def test_nivel_cresce_sem_pular_degrau():
    anterior = 1
    for experiencia in range(0, 5000, 7):
        nivel = nivel_para_experiencia(experiencia)
        assert nivel in (anterior, anterior + 1)
        anterior = nivel


def test_experiencia_negativa_e_recusada():
    with pytest.raises(ExperienciaInvalida):
        nivel_para_experiencia(-1)


@pytest.mark.parametrize("nivel", [0, -1, balance.NIVEL_MAXIMO + 1])
def test_nivel_fora_da_faixa_e_recusado(nivel):
    with pytest.raises(NivelDeTreinadorInvalido):
        experiencia_total_para_nivel(nivel)
    with pytest.raises(NivelDeTreinadorInvalido):
        exigir_nivel_de_treinador(nivel)


def test_quanto_falta_para_o_proximo_nivel():
    assert experiencia_para_o_proximo_nivel(0) == 60
    assert experiencia_para_o_proximo_nivel(59) == 1
    assert experiencia_para_o_proximo_nivel(60) == 180


def test_no_nivel_maximo_nao_existe_proximo_nivel():
    # None e nao zero: zero diria que falta nada, ou seja, que a proxima
    # experiencia faz subir. Mesmo contrato de PokemonDetalhe.
    assert experiencia_para_o_proximo_nivel(experiencia_total_para_nivel(100)) is None
    assert experiencia_para_o_proximo_nivel(10**9) is None


# --- Ganho por batalha (SDD 4.1) --------------------------------------------


@pytest.mark.parametrize(
    ("total_da_batalha", "esperado"),
    [
        # Um terco do total que a batalha gerou, antes da divisao entre o time.
        (0, 0),
        (1, 0),
        (3, 1),
        (30, 10),
        (100, 33),
        (999, 333),
    ],
)
def test_treinador_leva_um_terco_da_experiencia_da_batalha(total_da_batalha, esperado):
    assert experiencia_ganha_por_batalha(total_da_batalha) == esperado


def test_um_terco_exato_nao_perde_para_o_ponto_flutuante():
    # Com float, 3 * (1/3) nao fecha em 1 e o treinador perderia experiencia a
    # cada batalha redonda. A conta corre em Fraction exata.
    for multiplo in range(1, 500):
        assert experiencia_ganha_por_batalha(multiplo * 3) == multiplo


def test_ganho_do_treinador_independe_do_tamanho_do_time():
    # A base e a experiencia total da batalha, nao a parcela de cada Pokemon:
    # o tamanho do time e escolha tatica, nao imposto sobre a carreira.
    total = 210
    por_pokemon = {participantes: total // participantes for participantes in (1, 2, 3)}
    assert por_pokemon == {1: 210, 2: 105, 3: 70}
    assert {experiencia_ganha_por_batalha(total) for _ in por_pokemon} == {70}


def test_ganho_por_batalha_e_deterministico():
    primeira = [experiencia_ganha_por_batalha(total) for total in range(200)]
    segunda = [experiencia_ganha_por_batalha(total) for total in range(200)]
    assert primeira == segunda


def test_batalha_com_experiencia_negativa_e_recusada():
    with pytest.raises(ExperienciaInvalida):
        experiencia_ganha_por_batalha(-1)
