"""`repositories/treinadores.py`: eager loading do time e escopo por laboratorio.

O risco do plan.md da spec 004 e identico ao de `repositories/pokemon.py`
(spec 003): listar treinadores com o time e a especie de cada membro tem que
ser um numero FIXO de consultas, nao uma por treinador nem uma por Pokemon.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import event

from app.core.database import engine
from app.models import PokemonInstancia, Treinador
from app.repositories import laboratorios as laboratorios_repo
from app.repositories import professores as professores_repo
from app.repositories import treinadores as treinadores_repo


@contextmanager
def contar_consultas():
    contagem = {"total": 0}

    def _ouvir(conn, cursor, statement, parameters, context, executemany):
        contagem["total"] += 1

    event.listen(engine, "before_cursor_execute", _ouvir)
    try:
        yield contagem
    finally:
        event.remove(engine, "before_cursor_execute", _ouvir)


def _criar_laboratorio(sessao_db, sufixo: str) -> uuid.UUID:
    professor = professores_repo.criar(
        sessao_db,
        usuario=f"treinadores-repo-{sufixo}-{uuid.uuid4().hex[:8]}",
        senha_hash="x",
        nome_exibicao="Repo",
    )
    laboratorio = laboratorios_repo.criar(sessao_db, professor_id=professor.id, nome="Lab de teste")
    return laboratorio.id


def _criar_treinador(sessao_db, laboratorio_id: uuid.UUID, nome: str) -> uuid.UUID:
    treinador = Treinador(
        laboratorio_id=laboratorio_id,
        nome=nome,
        avatar={"iniciais": nome[:2].upper(), "cor": "#1f7a3f"},
        nivel=1,
        experiencia=0,
        status="DISPONIVEL",
    )
    sessao_db.add(treinador)
    sessao_db.flush()
    return treinador.id


def _inserir_pokemon(
    sessao_db,
    laboratorio_id: uuid.UUID,
    *,
    especie_id: int = 1,
    nivel: int = 5,
    treinador_id: uuid.UUID | None = None,
) -> uuid.UUID:
    pokemon = PokemonInstancia(
        laboratorio_id=laboratorio_id,
        especie_id=especie_id,
        nivel=nivel,
        experiencia=0,
        hp_atual_pct=100,
        treinador_id=treinador_id,
        origem="CAPTURADO",
        local_captura_id=None,
        capturado_em=datetime.now(UTC),
    )
    sessao_db.add(pokemon)
    sessao_db.flush()
    return pokemon.id


def test_listar_treinadores_com_time_cheio_usa_numero_fixo_de_consultas(sessao_db):
    """Tres treinadores com time cheio sao nove Pokemon e nove especies."""
    laboratorio_id = _criar_laboratorio(sessao_db, "listar")
    for indice in range(3):
        treinador_id = _criar_treinador(sessao_db, laboratorio_id, f"Treinador{indice}")
        for _ in range(3):
            _inserir_pokemon(sessao_db, laboratorio_id, treinador_id=treinador_id)
    sessao_db.commit()

    with contar_consultas() as contagem:
        treinadores = treinadores_repo.listar(sessao_db, laboratorio_id)
        # Acessar o time e a especie de cada membro nao pode disparar consulta
        # nova: ja vieram juntos via `selectinload` + `joinedload`.
        nomes_das_especies = [
            pokemon.especie.nome for treinador in treinadores for pokemon in treinador.time
        ]

    assert len(treinadores) == 3
    assert all(len(treinador.time) == 3 for treinador in treinadores)
    assert len(nomes_das_especies) == 9
    assert contagem["total"] <= 2


def test_buscar_detalhe_traz_o_time_e_a_especie_numa_consulta_fixa(sessao_db):
    laboratorio_id = _criar_laboratorio(sessao_db, "detalhe")
    treinador_id = _criar_treinador(sessao_db, laboratorio_id, "Ficha")
    for _ in range(3):
        _inserir_pokemon(sessao_db, laboratorio_id, treinador_id=treinador_id)
    sessao_db.commit()

    with contar_consultas() as contagem:
        treinador = treinadores_repo.buscar_detalhe(sessao_db, laboratorio_id, treinador_id)
        nomes = [pokemon.especie.nome for pokemon in treinador.time]

    assert treinador is not None
    assert len(nomes) == 3
    assert contagem["total"] <= 2


def test_buscar_detalhe_de_outro_laboratorio_devolve_none(sessao_db):
    lab_a = _criar_laboratorio(sessao_db, "escopo-a")
    lab_b = _criar_laboratorio(sessao_db, "escopo-b")
    treinador_de_b = _criar_treinador(sessao_db, lab_b, "DeOutroLab")
    sessao_db.commit()

    encontrado = treinadores_repo.buscar_detalhe(sessao_db, lab_a, treinador_de_b)

    assert encontrado is None


def test_pokemon_envolvidos_traz_pedidos_e_time_atual_sem_duplicar(sessao_db):
    laboratorio_id = _criar_laboratorio(sessao_db, "envolvidos")
    treinador_id = _criar_treinador(sessao_db, laboratorio_id, "Alvo")
    no_time = _inserir_pokemon(sessao_db, laboratorio_id, treinador_id=treinador_id)
    livre = _inserir_pokemon(sessao_db, laboratorio_id)
    sessao_db.commit()

    # Pede o que ja esta no time (de novo) e o livre: a uniao nao duplica
    # `no_time`, mesmo aparecendo nas duas metades da condicao.
    envolvidos = treinadores_repo.buscar_pokemon_envolvidos(
        sessao_db, laboratorio_id, treinador_id, [no_time, livre]
    )

    assert {pokemon.id for pokemon in envolvidos} == {no_time, livre}
