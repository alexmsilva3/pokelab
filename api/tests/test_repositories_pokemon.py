"""`repositories/pokemon.py`: filtros, paginacao deterministica e a consulta.

O risco do plan.md da spec 003 e volume: listar com a especie junta tem que
ser UMA consulta por pagina, nao uma por item. `contar_consultas` instrumenta
o engine para provar isso com um numero, nao por inspecao de codigo.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import event

from app.core.database import engine
from app.models import PokemonInstancia, Treinador
from app.repositories import laboratorios as laboratorios_repo
from app.repositories import pokemon as pokemon_repo
from app.repositories import professores as professores_repo
from app.repositories.pokemon import PAGE_SIZE_MAXIMO, FiltrosPokemon


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


def _criar_laboratorio(sessao_db) -> uuid.UUID:
    """Devolve so o id, ja capturado antes de qualquer `commit()`.

    `commit()` expira os atributos do objeto por padrao: ler `.id` depois
    disso dispara um SELECT de recarga, que contaminaria qualquer contagem de
    consultas feita por quem chama este helper.
    """
    professor = professores_repo.criar(
        sessao_db, usuario=f"repo-{uuid.uuid4().hex[:12]}", senha_hash="x", nome_exibicao="Repo"
    )
    laboratorio = laboratorios_repo.criar(sessao_db, professor_id=professor.id, nome="Lab de teste")
    return laboratorio.id


def _inserir_pokemon(
    sessao_db,
    laboratorio_id: uuid.UUID,
    *,
    especie_id: int,
    nivel: int,
    treinador_id: uuid.UUID | None = None,
) -> PokemonInstancia:
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
    return pokemon


def test_listagem_com_muitos_pokemon_usa_exatamente_duas_consultas(sessao_db):
    """Join unico: a quantidade de consultas nao cresce com o tamanho da pagina."""
    laboratorio_id = _criar_laboratorio(sessao_db)
    for _ in range(30):
        _inserir_pokemon(sessao_db, laboratorio_id, especie_id=1, nivel=10)
    sessao_db.commit()

    with contar_consultas() as contagem:
        itens, total, page, page_size = pokemon_repo.listar(
            sessao_db, laboratorio_id, FiltrosPokemon(), page=1, page_size=20
        )
        # Acessar a especie de cada item nao pode disparar consulta nova: ja
        # veio junta na mesma consulta via `contains_eager`.
        nomes = [item.especie.nome for item in itens]

    assert contagem["total"] == 2
    assert total == 30
    assert len(itens) == 20
    assert page == 1
    assert page_size == 20
    assert nomes == ["Bulbasaur"] * 20


def test_paginacao_e_deterministica_sem_lacuna_nem_repeticao(sessao_db):
    laboratorio_id = _criar_laboratorio(sessao_db)
    for _ in range(25):
        _inserir_pokemon(sessao_db, laboratorio_id, especie_id=1, nivel=10)
    sessao_db.commit()

    pagina1, total1, _, _ = pokemon_repo.listar(
        sessao_db, laboratorio_id, FiltrosPokemon(), page=1, page_size=10
    )
    pagina2, total2, _, _ = pokemon_repo.listar(
        sessao_db, laboratorio_id, FiltrosPokemon(), page=2, page_size=10
    )
    pagina3, total3, _, _ = pokemon_repo.listar(
        sessao_db, laboratorio_id, FiltrosPokemon(), page=3, page_size=10
    )

    ids_vistos = [p.id for p in pagina1] + [p.id for p in pagina2] + [p.id for p in pagina3]
    assert total1 == total2 == total3 == 25
    assert len(pagina1) == 10
    assert len(pagina2) == 10
    assert len(pagina3) == 5
    assert len(set(ids_vistos)) == 25  # nenhum repetido, nenhum faltando


def test_page_size_acima_do_teto_e_cortado_em_silencio(sessao_db):
    laboratorio_id = _criar_laboratorio(sessao_db)
    _inserir_pokemon(sessao_db, laboratorio_id, especie_id=1, nivel=5)
    sessao_db.commit()

    _, _, _, page_size = pokemon_repo.listar(
        sessao_db, laboratorio_id, FiltrosPokemon(), page=1, page_size=9999
    )

    assert page_size == PAGE_SIZE_MAXIMO


def test_filtro_por_tipo_casa_com_tipo_secundario(sessao_db):
    """Bulbasaur (grass/poison): filtrar por 'poison' tem que traze-lo (criterio 3)."""
    laboratorio_id = _criar_laboratorio(sessao_db)
    bulbasaur = _inserir_pokemon(sessao_db, laboratorio_id, especie_id=1, nivel=5)  # grass/poison
    _inserir_pokemon(sessao_db, laboratorio_id, especie_id=4, nivel=5)  # charmander: fire
    sessao_db.commit()

    itens, total, _, _ = pokemon_repo.listar(
        sessao_db, laboratorio_id, FiltrosPokemon(tipo="poison"), page=1, page_size=20
    )

    assert total == 1
    assert itens[0].id == bulbasaur.id


def test_filtros_de_tipo_e_nivel_combinam(sessao_db):
    """Criterio 4: tipo e faixa de nivel aplicados juntos satisfazem os dois."""
    laboratorio_id = _criar_laboratorio(sessao_db)
    _inserir_pokemon(sessao_db, laboratorio_id, especie_id=1, nivel=5)  # grass, nivel baixo
    alvo = _inserir_pokemon(sessao_db, laboratorio_id, especie_id=1, nivel=40)  # grass, nivel alto
    _inserir_pokemon(sessao_db, laboratorio_id, especie_id=4, nivel=40)  # fire, nivel alto
    sessao_db.commit()

    itens, total, _, _ = pokemon_repo.listar(
        sessao_db,
        laboratorio_id,
        FiltrosPokemon(tipo="grass", nivel_min=30, nivel_max=50),
        page=1,
        page_size=20,
    )

    assert total == 1
    assert itens[0].id == alvo.id


def test_filtro_atribuido_tres_estados(sessao_db):
    laboratorio_id = _criar_laboratorio(sessao_db)
    treinador = Treinador(
        laboratorio_id=laboratorio_id,
        nome="Ash",
        avatar={"iniciais": "AS", "cor": "#000000"},
        nivel=1,
        experiencia=0,
        status="DISPONIVEL",
    )
    sessao_db.add(treinador)
    sessao_db.flush()
    treinador_id = treinador.id

    livre = _inserir_pokemon(sessao_db, laboratorio_id, especie_id=1, nivel=5)
    no_time = _inserir_pokemon(
        sessao_db, laboratorio_id, especie_id=1, nivel=5, treinador_id=treinador_id
    )
    sessao_db.commit()

    _, total_sem, _, _ = pokemon_repo.listar(
        sessao_db, laboratorio_id, FiltrosPokemon(), page=1, page_size=20
    )
    so_atribuidos, _, _, _ = pokemon_repo.listar(
        sessao_db, laboratorio_id, FiltrosPokemon(atribuido=True), page=1, page_size=20
    )
    so_livres, _, _, _ = pokemon_repo.listar(
        sessao_db, laboratorio_id, FiltrosPokemon(atribuido=False), page=1, page_size=20
    )

    assert total_sem == 2
    assert [p.id for p in so_atribuidos] == [no_time.id]
    assert [p.id for p in so_livres] == [livre.id]


def test_listagem_e_escopada_ao_laboratorio(sessao_db):
    lab_a = _criar_laboratorio(sessao_db)
    professor_b = professores_repo.criar(
        sessao_db,
        usuario=f"outro-repo-{uuid.uuid4().hex[:8]}",
        senha_hash="x",
        nome_exibicao="Outro",
    )
    lab_b = laboratorios_repo.criar(sessao_db, professor_id=professor_b.id, nome="Outro lab").id
    _inserir_pokemon(sessao_db, lab_a, especie_id=1, nivel=5)
    _inserir_pokemon(sessao_db, lab_b, especie_id=1, nivel=5)
    sessao_db.commit()

    _, total, _, _ = pokemon_repo.listar(sessao_db, lab_a, FiltrosPokemon(), page=1, page_size=20)

    assert total == 1


def test_buscar_detalhe_de_outro_laboratorio_devolve_none(sessao_db):
    lab_a = _criar_laboratorio(sessao_db)
    professor_b = professores_repo.criar(
        sessao_db,
        usuario=f"detalhe-outro-{uuid.uuid4().hex[:8]}",
        senha_hash="x",
        nome_exibicao="Outro",
    )
    lab_b = laboratorios_repo.criar(sessao_db, professor_id=professor_b.id, nome="Outro lab 2").id
    pokemon_de_b = _inserir_pokemon(sessao_db, lab_b, especie_id=1, nivel=5)
    sessao_db.commit()

    encontrado = pokemon_repo.buscar_detalhe(sessao_db, lab_a, pokemon_de_b.id)

    assert encontrado is None
