"""Soltar um Pokemon: as recusas e o que soltar NAO rende (spec 008, SDD 4.10).

Cada recusa tem teste proprio e confere o CODIGO, nao so o fato de levantar.
"Nao da para soltar" nao e frase util numa tela, e um teste que aceitasse
qualquer `ErroDeSoltura` deixaria passar o dia em que as tres recusas viraram
uma so.

O teste da ordem existe porque mais de uma recusa pode valer ao mesmo tempo —
o ultimo Pokemon do laboratorio pode estar em expedicao — e a mensagem que o
professor le depende de qual vence.
"""

from uuid import UUID, uuid4

import pytest

from app.game import balance
from app.game.soltar import (
    ErroDeSoltura,
    EstadoInconsistente,
    PokemonComprometido,
    PokemonEmExpedicao,
    PreviaDeSoltura,
    TreinadorDoPokemon,
    TreinadorEmEntrega,
    UltimoPokemon,
    exigir_que_sobre_pokemon,
    pode_soltar,
    prever_soltura,
)
from app.game.trainers import StatusTreinador
from app.game.viveiro import PokemonDoLaboratorio

TREINADOR_ID = UUID(int=7)
ENTREGA_ID = UUID(int=99)

ACERVO_FOLGADO = 12


def treinador(status: StatusTreinador) -> TreinadorDoPokemon:
    return TreinadorDoPokemon(id=TREINADOR_ID, nome="Kenji", status=status)


def no_viveiro() -> PokemonDoLaboratorio:
    return PokemonDoLaboratorio(id=uuid4())


def no_time() -> PokemonDoLaboratorio:
    return PokemonDoLaboratorio(id=uuid4(), treinador_id=TREINADOR_ID)


def comprometido() -> PokemonDoLaboratorio:
    return PokemonDoLaboratorio(id=uuid4(), comprometido_entrega_id=ENTREGA_ID)


# --- 1. O caso normal (criterios 6 e 8) -------------------------------------


def test_solta_um_pokemon_do_viveiro():
    assert pode_soltar(no_viveiro(), None, ACERVO_FOLGADO) is None


def test_solta_um_pokemon_do_time_de_um_treinador_disponivel():
    # Criterio 8: o time encolhe. O Pokemon esta no laboratorio, e o treinador
    # nao esta em missao nenhuma.
    assert pode_soltar(no_time(), treinador(StatusTreinador.DISPONIVEL), ACERVO_FOLGADO) is None


def test_solta_um_pokemon_do_time_de_um_treinador_descansando():
    # DESCANSANDO nao e ocupado (SDD 3.3, invariante 3): o treinador voltou e
    # o professor pode remontar o time dele.
    assert pode_soltar(no_time(), treinador(StatusTreinador.DESCANSANDO), ACERVO_FOLGADO) is None


def test_soltar_com_exatamente_dois_pokemon_e_permitido():
    # A borda de cima do invariante 25: sobra um, e um basta.
    assert pode_soltar(no_viveiro(), None, balance.POKEMON_MINIMOS_NO_LABORATORIO + 1) is None


# --- 2. As recusas, cada uma com o codigo dela (criterios 9 a 11) -----------


def test_recusa_soltar_pokemon_em_expedicao():
    with pytest.raises(PokemonEmExpedicao) as erro:
        pode_soltar(no_time(), treinador(StatusTreinador.EM_EXPEDICAO), ACERVO_FOLGADO)

    assert erro.value.codigo == "POKEMON_EM_EXPEDICAO"
    assert erro.value.detalhes["treinador_nome"] == "Kenji"
    assert erro.value.detalhes["status_treinador"] == "EM_EXPEDICAO"


def test_recusa_soltar_pokemon_comprometido_com_entrega():
    with pytest.raises(PokemonComprometido) as erro:
        pode_soltar(comprometido(), None, ACERVO_FOLGADO)

    assert erro.value.codigo == "POKEMON_COMPROMETIDO"
    assert erro.value.detalhes["entrega_id"] == str(ENTREGA_ID)


def test_recusa_soltar_o_ultimo_pokemon_do_laboratorio():
    # Criterio 11 e invariante 25: sem Pokemon nao ha time, sem time nao ha
    # expedicao, e os iniciais sao concedidos uma vez so. Esta porta nao
    # reabre, e por isso ela nem chega a abrir.
    with pytest.raises(UltimoPokemon) as erro:
        pode_soltar(no_viveiro(), None, 1)

    assert erro.value.codigo == "ULTIMO_POKEMON"
    assert erro.value.detalhes["minimo"] == balance.POKEMON_MINIMOS_NO_LABORATORIO


def test_recusa_soltar_do_time_de_um_treinador_em_entrega():
    # Invariantes 3 e 4: o time de um treinador ocupado nao muda. O Pokemon
    # nao e `comprometido` — os comprometidos sao os Pokemon PEDIDOS —, mas
    # viaja com o mensageiro e tambem nao esta no laboratorio.
    with pytest.raises(TreinadorEmEntrega) as erro:
        pode_soltar(no_time(), treinador(StatusTreinador.EM_ENTREGA), ACERVO_FOLGADO)

    assert erro.value.codigo == "TREINADOR_OCUPADO"


def test_as_tres_recusas_tem_codigos_distintos():
    codigos = {PokemonEmExpedicao.codigo, PokemonComprometido.codigo, UltimoPokemon.codigo}

    assert len(codigos) == 3


# --- 3. A ordem das recusas quando mais de uma vale -------------------------


def test_o_pokemon_em_expedicao_vence_o_ultimo_pokemon():
    # O obstaculo mais imediato primeiro: dizer "e o ultimo" de um Pokemon que
    # esta em campo mandaria o professor soltar outro, que tambem nao resolve.
    with pytest.raises(PokemonEmExpedicao):
        pode_soltar(no_time(), treinador(StatusTreinador.EM_EXPEDICAO), 1)


def test_o_pokemon_comprometido_vence_o_ultimo_pokemon():
    with pytest.raises(PokemonComprometido):
        pode_soltar(comprometido(), None, 1)


# --- 4. Chamada incoerente e erro de programa, nao de jogo ------------------


def test_recusa_quando_o_treinador_do_pokemon_nao_foi_informado():
    with pytest.raises(EstadoInconsistente):
        pode_soltar(no_time(), None, ACERVO_FOLGADO)


def test_recusa_quando_o_treinador_informado_e_outro():
    outro = TreinadorDoPokemon(id=UUID(int=8), nome="Lari", status=StatusTreinador.DISPONIVEL)

    with pytest.raises(EstadoInconsistente):
        pode_soltar(no_time(), outro, ACERVO_FOLGADO)


def test_total_do_laboratorio_negativo_e_chamada_errada():
    with pytest.raises(EstadoInconsistente):
        exigir_que_sobre_pokemon(-1)


# --- 5. A guarda do ultimo Pokemon e reusada, nao copiada -------------------


@pytest.mark.parametrize(
    ("total", "saindo"),
    [(2, 1), (5, 4), (12, 11), (2, 0)],
)
def test_a_guarda_passa_enquanto_sobra_pokemon(total, saindo):
    assert exigir_que_sobre_pokemon(total, saindo) is None


@pytest.mark.parametrize(
    ("total", "saindo"),
    [(1, 1), (3, 3), (3, 4), (0, 0)],
)
def test_a_guarda_recusa_quando_o_laboratorio_ficaria_vazio(total, saindo):
    # O aceite de entrega chama com quantos Pokemon o pedido leva: tres de uma
    # vez num laboratorio de tres esvaziaria o lugar de uma so operacao, e e
    # por isso que a guarda recebe `saindo` em vez de supor 1.
    with pytest.raises(UltimoPokemon):
        exigir_que_sobre_pokemon(total, saindo)


def test_a_guarda_do_aceite_leva_o_tamanho_do_pedido_nos_detalhes():
    with pytest.raises(UltimoPokemon) as erro:
        exigir_que_sobre_pokemon(3, 3)

    assert erro.value.detalhes["total_do_laboratorio"] == 3
    assert erro.value.detalhes["saindo"] == 3


# --- 6. A previa valida pelo mesmo caminho ----------------------------------


def test_a_previa_aprova_o_que_pode_soltar_aprova():
    previa = prever_soltura(no_viveiro(), None, ACERVO_FOLGADO)

    assert previa == PreviaDeSoltura(permitido=True)


def test_a_previa_devolve_o_codigo_em_vez_de_levantar():
    previa = prever_soltura(comprometido(), None, ACERVO_FOLGADO)

    assert previa.permitido is False
    assert previa.codigo == "POKEMON_COMPROMETIDO"
    assert previa.motivo
    assert previa.detalhes is not None
    assert previa.detalhes["entrega_id"] == str(ENTREGA_ID)


def test_a_previa_e_o_soltar_nunca_discordam():
    # Previa e escrita que validam por caminhos diferentes divergem no
    # primeiro invariante novo, e o professor leva um erro no botao que a
    # previa jurava que nao existia.
    casos = [
        (no_viveiro(), None, ACERVO_FOLGADO),
        (no_viveiro(), None, 1),
        (comprometido(), None, ACERVO_FOLGADO),
        (no_time(), treinador(StatusTreinador.EM_EXPEDICAO), ACERVO_FOLGADO),
        (no_time(), treinador(StatusTreinador.EM_ENTREGA), ACERVO_FOLGADO),
        (no_time(), treinador(StatusTreinador.DISPONIVEL), ACERVO_FOLGADO),
    ]

    for pokemon, dono, total in casos:
        previa = prever_soltura(pokemon, dono, total)
        if previa.permitido:
            assert pode_soltar(pokemon, dono, total) is None
        else:
            with pytest.raises(ErroDeSoltura) as erro:
                pode_soltar(pokemon, dono, total)
            assert erro.value.codigo == previa.codigo


# --- 7. Soltar nao rende nada (SDD 4.10) ------------------------------------


def test_soltar_nao_devolve_recompensa_nenhuma():
    # Deliberado: se soltar rendesse moeda, soltar viraria a forma otima de
    # jogar o excedente fora e a Central de Entregas perderia a razao de
    # existir. O dominio so responde "pode?" — nao ha saida para gravar.
    assert pode_soltar(no_viveiro(), None, ACERVO_FOLGADO) is None


def test_o_modulo_de_soltura_nao_conhece_moeda_nem_experiencia():
    from app.game import soltar

    nomes = dir(soltar)
    assert not [n for n in nomes if "moeda" in n.lower() or "recompensa" in n.lower()]
    assert not [n for n in nomes if "experiencia" in n.lower()]
