"""Progressao do laboratorio (SDD 4.1)."""

from __future__ import annotations

import pytest

from app.game import balance
from app.game.laboratorio import (
    NivelDeLaboratorioInvalido,
    experiencia_total_para_nivel,
    limite_treinadores,
    nivel_para_experiencia,
)


def test_laboratorio_nivel_1_comporta_tres_treinadores():
    assert limite_treinadores(1) == 3


@pytest.mark.parametrize(("nivel", "esperado"), [(1, 3), (2, 4), (5, 7), (10, 12)])
def test_cada_nivel_acrescenta_um_treinador(nivel, esperado):
    assert limite_treinadores(nivel) == esperado


def test_kit_inicial_cabe_dentro_do_limite_do_nivel_1():
    # Conceder mais treinadores do que o laboratorio comporta tornaria o
    # invariante 5 falso logo no registro.
    assert limite_treinadores(1) >= balance.TREINADORES_NO_KIT_INICIAL


def test_nivel_zero_e_recusado():
    with pytest.raises(NivelDeLaboratorioInvalido):
        limite_treinadores(0)


def test_laboratorio_nasce_sem_experiencia():
    assert experiencia_total_para_nivel(1) == 0


def test_experiencia_e_nivel_sao_inversos():
    for nivel in range(1, 21):
        assert nivel_para_experiencia(experiencia_total_para_nivel(nivel)) == nivel


def test_experiencia_logo_abaixo_do_corte_nao_sobe_de_nivel():
    for nivel in range(2, 21):
        assert nivel_para_experiencia(experiencia_total_para_nivel(nivel) - 1) == nivel - 1


def test_experiencia_negativa_e_recusada():
    with pytest.raises(NivelDeLaboratorioInvalido):
        nivel_para_experiencia(-1)
