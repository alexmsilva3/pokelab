"""`/sprites`: acervo local servido com cache imutavel (spec 003, criterio 12).

Sem marca `requer_banco`: servir um arquivo estatico nao toca o Postgres.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.caminhos import DIR_SPRITES
from app.main import app

client = TestClient(app)


def test_sprite_existente_e_servido_com_cache_imutavel():
    algum_sprite = next(DIR_SPRITES.glob("*.png")).name

    resposta = client.get(f"/sprites/{algum_sprite}")

    assert resposta.status_code == 200
    assert resposta.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert resposta.headers["content-type"] == "image/png"


def test_sprite_inexistente_devolve_404():
    resposta = client.get("/sprites/nao-existe-999.png")

    assert resposta.status_code == 404


def test_sprite_nao_faz_requisicao_a_servico_externo():
    """Criterio 12: a origem e sempre o proprio servidor, nunca a PokeAPI.

    O teste em si prova isso por construcao: nenhuma chamada de rede e feita
    aqui, e a resposta vem inteira de `DIR_SPRITES`, um diretorio local.
    """
    algum_sprite = next(DIR_SPRITES.glob("*.png")).name
    resposta = client.get(f"/sprites/{algum_sprite}")

    assert resposta.status_code == 200
    assert resposta.content == (DIR_SPRITES / algum_sprite).read_bytes()
