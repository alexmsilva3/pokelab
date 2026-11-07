"""Materializacao do kit inicial no banco (spec 002, regras 6 a 9; criterio 1).

`tests/test_game_kit_inicial.py` ja cobre o dominio puro, sem banco algum
(Artigo I). Este arquivo cobre a outra ponta: o que `services/auth.py` e
`repositories/kit_inicial.py` realmente gravam quando o professor se
registra, seguindo o mesmo padrao de `test_seed_carga.py` para testes que
exigem Postgres.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.erros import KitJaConcedido, UsuarioEmUso
from app.game import balance
from app.models import (
    ItemEstoque,
    Laboratorio,
    LocalDesbloqueado,
    PokedexEntrada,
    PokemonInstancia,
    Treinador,
)
from app.services import auth as auth_service
from tests.conftest import requer_banco

pytestmark = requer_banco


def _contagens(sessao_db, laboratorio_id):
    return {
        "pokemon": len(
            sessao_db.scalars(
                select(PokemonInstancia).where(PokemonInstancia.laboratorio_id == laboratorio_id)
            ).all()
        ),
        "treinadores": len(
            sessao_db.scalars(
                select(Treinador).where(Treinador.laboratorio_id == laboratorio_id)
            ).all()
        ),
        "itens": len(
            sessao_db.scalars(
                select(ItemEstoque).where(ItemEstoque.laboratorio_id == laboratorio_id)
            ).all()
        ),
        "locais": len(
            sessao_db.scalars(
                select(LocalDesbloqueado).where(LocalDesbloqueado.laboratorio_id == laboratorio_id)
            ).all()
        ),
        "pokedex": len(
            sessao_db.scalars(
                select(PokedexEntrada).where(PokedexEntrada.laboratorio_id == laboratorio_id)
            ).all()
        ),
    }


def test_registro_grava_o_laboratorio_zerado_conforme_a_regra_6(sessao_db):
    """Regra 6: o laboratorio nasce no nivel 1, com zero experiencia e zero
    moedas."""
    resultado = auth_service.registrar(sessao_db, usuario="Lugia", senha="guardiao12345")

    assert resultado.laboratorio.nivel == 1
    assert resultado.laboratorio.experiencia == 0
    assert resultado.laboratorio.moedas == 0
    assert resultado.laboratorio.starters_concedidos is True


def test_registro_grava_os_tres_iniciais_no_nivel_do_balance(sessao_db):
    """Regras 7 e 8: os tres iniciais sao Bulbasaur, Charmander e Squirtle,
    no nivel declarado em `balance.STARTER_LEVEL`."""
    resultado = auth_service.registrar(sessao_db, usuario="Hooh", senha="fenixarco1234")

    pokemon = sessao_db.scalars(
        select(PokemonInstancia).where(PokemonInstancia.laboratorio_id == resultado.laboratorio.id)
    ).all()

    assert len(pokemon) == 3
    assert {p.especie_id for p in pokemon} == set(balance.STARTER_SPECIES_IDS)
    assert all(p.nivel == balance.STARTER_LEVEL for p in pokemon)
    assert all(p.hp_atual_pct == 100 for p in pokemon)
    assert all(p.origem == "INICIAL" for p in pokemon)


def test_registro_grava_o_treinador_inicial_sem_pokemon_no_time(sessao_db):
    """Regra 9: o treinador inicial chega sem Pokemon no time -- montar o
    time e decisao do professor, nao algo que o registro resolve por ele."""
    resultado = auth_service.registrar(sessao_db, usuario="Entei", senha="leaoardente12")

    treinadores = sessao_db.scalars(
        select(Treinador).where(Treinador.laboratorio_id == resultado.laboratorio.id)
    ).all()
    pokemon = sessao_db.scalars(
        select(PokemonInstancia).where(PokemonInstancia.laboratorio_id == resultado.laboratorio.id)
    ).all()

    assert len(treinadores) == balance.TREINADORES_NO_KIT_INICIAL
    assert all(t.nivel == 1 for t in treinadores)
    assert all(t.status == "DISPONIVEL" for t in treinadores)
    # Nenhum starter aponta para um treinador: o time comeca vazio.
    assert all(p.treinador_id is None for p in pokemon)


def test_registro_grava_o_estoque_inicial_identico_ao_balance_sem_quantidade_negativa(sessao_db):
    """Regra 7 e invariante 9 do SDD 3.3: o estoque nasce exatamente como
    `balance.ESTOQUE_INICIAL` descreve, e nunca negativo."""
    resultado = auth_service.registrar(sessao_db, usuario="Raikou", senha="trovaoveloz12")

    itens = sessao_db.scalars(
        select(ItemEstoque).where(ItemEstoque.laboratorio_id == resultado.laboratorio.id)
    ).all()

    assert {item.item_id: item.quantidade for item in itens} == balance.ESTOQUE_INICIAL
    assert all(item.quantidade >= 0 for item in itens)


def test_registro_desbloqueia_apenas_pallet_town(sessao_db):
    """Regra 7: Pallet Town e desbloqueada na criacao da conta, e nenhum
    outro local."""
    resultado = auth_service.registrar(sessao_db, usuario="Suicune", senha="correntedeagua1")

    locais = sessao_db.scalars(
        select(LocalDesbloqueado).where(
            LocalDesbloqueado.laboratorio_id == resultado.laboratorio.id
        )
    ).all()

    assert [local.local_id for local in locais] == [balance.LOCAL_INICIAL_ID]


def test_registro_marca_apenas_os_tres_iniciais_como_vistos_e_capturados_na_pokedex(sessao_db):
    """Regra 8: os tres iniciais entram na Pokedex como capturados -- e
    nenhuma outra especie."""
    resultado = auth_service.registrar(sessao_db, usuario="Celebi", senha="viajantetempo1")

    pokedex = sessao_db.scalars(
        select(PokedexEntrada).where(PokedexEntrada.laboratorio_id == resultado.laboratorio.id)
    ).all()

    assert {entrada.especie_id for entrada in pokedex} == set(balance.STARTER_SPECIES_IDS)
    assert all(entrada.visto and entrada.capturado for entrada in pokedex)


# --- Idempotencia do kit (item 6 da lista de obrigacoes da constituicao) ---


def test_kit_e_concedido_uma_unica_vez_por_laboratorio(sessao_db):
    """Invariante 10 do SDD 3.3: os starters sao concedidos exatamente uma
    vez por laboratorio.

    Diferente do teste de concorrencia (que dispara duas tentativas ao
    mesmo tempo), este cobre o caso sequencial: depois que o laboratorio ja
    nasceu com o kit, nenhuma tentativa seguinte de registrar o mesmo
    usuario -- concorrente ou nao -- consegue conceder um segundo kit.
    Nenhum mecanismo do sistema permite reconceder starters para um
    laboratorio que ja os tem.
    """
    resultado = auth_service.registrar(sessao_db, usuario="Articuno", senha="geloeterno123")
    laboratorio_id = resultado.laboratorio.id
    antes = _contagens(sessao_db, laboratorio_id)

    with pytest.raises(UsuarioEmUso):
        auth_service.registrar(sessao_db, usuario="ARTICUNO", senha="outrasenha1234")

    depois = _contagens(sessao_db, laboratorio_id)

    assert (
        antes
        == depois
        == {
            "pokemon": len(balance.STARTER_SPECIES_IDS),
            "treinadores": balance.TREINADORES_NO_KIT_INICIAL,
            "itens": len(balance.ESTOQUE_INICIAL),
            "locais": 1,
            "pokedex": len(balance.STARTER_SPECIES_IDS),
        }
    )
    assert sessao_db.get(Laboratorio, laboratorio_id).starters_concedidos is True


# --- Regressao da revisao da Fase 2: guarda de `_conceder_kit` em si --------
# ALTO: `starters_concedidos` era escrito e nunca lido. Uma segunda concessao
# sobre o MESMO laboratorio adicionava tres Pokemon e um treinador extras
# antes de estourar na chave composta de item_estoques, com IntegrityError
# vazando. Diferente do teste acima (que passa pelo `registrar()` publico
# com um usuario duplicado), estes dois chamam `_conceder_kit` direto sobre
# um laboratorio que ja tem o kit, provando que a guarda vive na propria
# concessao, nao so na checagem de usuario em uso.


def test_segunda_concessao_do_kit_e_recusada(sessao_db):
    criada = auth_service.registrar(sessao_db, usuario="kit2x", senha="senhavalida123")
    laboratorio = sessao_db.get(Laboratorio, criada.laboratorio.id)

    with pytest.raises(KitJaConcedido):
        auth_service._conceder_kit(sessao_db, laboratorio)
    sessao_db.rollback()


def test_segunda_concessao_nao_cria_pokemon_nem_treinador_extra(sessao_db):
    criada = auth_service.registrar(sessao_db, usuario="kitextra", senha="senhavalida123")
    laboratorio_id = criada.laboratorio.id

    def contar(modelo) -> int:
        return len(
            sessao_db.scalars(select(modelo).where(modelo.laboratorio_id == laboratorio_id)).all()
        )

    antes = (contar(PokemonInstancia), contar(Treinador))

    with pytest.raises(KitJaConcedido):
        auth_service._conceder_kit(sessao_db, sessao_db.get(Laboratorio, laboratorio_id))
    sessao_db.rollback()

    assert (contar(PokemonInstancia), contar(Treinador)) == antes
    assert antes == (len(balance.STARTER_SPECIES_IDS), balance.TREINADORES_NO_KIT_INICIAL)


# --- Regressao da revisao da Fase 2: semente do kit fica gravada ------------
# ALTO: o servico chamava random.Random() sem semente, contrariando o
# Artigo III: o kit de um laboratorio existente nao podia ser remontado.


def test_semente_do_kit_fica_gravada_no_laboratorio(sessao_db):
    criada = auth_service.registrar(sessao_db, usuario="semente", senha="senhavalida123")
    laboratorio = sessao_db.get(Laboratorio, criada.laboratorio.id)

    assert laboratorio.semente_kit_inicial is not None
    assert 0 <= laboratorio.semente_kit_inicial < auth_service.SEMENTE_MAXIMA


def test_a_semente_gravada_remonta_o_mesmo_kit(sessao_db):
    import random

    from app.game.kit_inicial import EspecieInicial, montar_kit_inicial
    from app.repositories import especies as especies_repo

    criada = auth_service.registrar(sessao_db, usuario="remonta", senha="senhavalida123")
    laboratorio = sessao_db.get(Laboratorio, criada.laboratorio.id)

    especies = [
        EspecieInicial(id=e.id, nome=e.nome, curva_crescimento=e.curva_crescimento)
        for e in especies_repo.buscar_iniciais(sessao_db)
    ]
    remontado = montar_kit_inicial(especies, random.Random(laboratorio.semente_kit_inicial))

    treinador_no_banco = sessao_db.scalars(
        select(Treinador).where(Treinador.laboratorio_id == laboratorio.id)
    ).first()
    assert remontado.treinadores[0].nome == treinador_no_banco.nome
