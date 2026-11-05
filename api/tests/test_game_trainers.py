"""Geracao de treinador: nome sorteado e avatar derivado (questao 16).

O ponto sensivel aqui e o Artigo III. Nome e avatar precisam ser os mesmos em
qualquer processo, em qualquer maquina, hoje e depois do proximo deploy.
"""

import random
import re
import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.game.erros import AvatarInvalido
from app.game.trainers import (
    NOMES_DE_TREINADOR,
    PALETA_AVATAR,
    Avatar,
    gerar_avatar,
    gerar_nome,
    gerar_treinador,
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
    assert avatar.para_dicionario() == {"iniciais": "KA", "cor": avatar.cor}


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
    assert Avatar(iniciais="AB", cor="#1f7a3f").para_dicionario() == {
        "iniciais": "AB",
        "cor": "#1f7a3f",
    }
