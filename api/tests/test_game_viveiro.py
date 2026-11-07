"""O viveiro: ocupacao derivada, transbordo e a guarda do despacho (spec 008).

Dois grupos de teste carregam o peso. O primeiro fixa a CONTAGEM — quem ocupa
lugar e quem nao ocupa —, porque e dela que saem todos os outros numeros. O
segundo fixa a regra mais importante da fase: transbordado, o viveiro trava o
despacho e **nada mais**. O teste que prova isso nao olha um resultado, olha o
codigo-fonte: ele varre `app/` atras de chamadas a guarda e reprova a que
aparecer num caminho de saida.
"""

import ast
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.game import balance
from app.game.viveiro import (
    OcupacaoInvalida,
    PokemonDoLaboratorio,
    ViveiroTransbordado,
    estado_do_viveiro,
    exigir_espaco_para_despachar,
    lugares_faltando,
    ocupacao,
    transbordado,
)

TREINADOR = UUID(int=7)
OUTRO_TREINADOR = UUID(int=8)
ENTREGA = UUID(int=99)


def guardado() -> PokemonDoLaboratorio:
    """Um Pokemon no viveiro: sem treinador e sem entrega."""
    return PokemonDoLaboratorio(id=uuid4())


def no_time(treinador_id: UUID = TREINADOR) -> PokemonDoLaboratorio:
    """Um Pokemon no time de alguem: viaja com o treinador."""
    return PokemonDoLaboratorio(id=uuid4(), treinador_id=treinador_id)


def comprometido() -> PokemonDoLaboratorio:
    """Um Pokemon prometido a uma entrega, ainda no laboratorio."""
    return PokemonDoLaboratorio(id=uuid4(), comprometido_entrega_id=ENTREGA)


# --- 1. Ocupacao: quem conta e quem nao conta (criterios 1 e 2) -------------


def test_o_viveiro_vazio_tem_ocupacao_zero():
    assert ocupacao([]) == 0


def test_ocupacao_conta_quem_tem_treinador_nulo():
    assert ocupacao([guardado(), guardado(), guardado()]) == 3


def test_ocupacao_ignora_quem_esta_em_time():
    # Criterio 2: um time de tres nao ocupa lugar nenhum — eles viajam com o
    # treinador, e e por isso que o invariante 20 fala de `treinador_id` nulo
    # e nao do total de Pokemon do laboratorio.
    acervo = [guardado(), no_time(), no_time(), no_time()]

    assert ocupacao(acervo) == 1


def test_ocupacao_ignora_times_de_treinadores_diferentes():
    acervo = [no_time(TREINADOR), no_time(OUTRO_TREINADOR), guardado()]

    assert ocupacao(acervo) == 1


def test_ocupacao_conta_quem_esta_comprometido_com_entrega():
    # Comprometido continua no laboratorio ate a entrega concluir, e o lugar
    # so volta ali. Descontar antes faria o professor despachar uma expedicao
    # contando com um espaco que ainda nao existe.
    acervo = [comprometido(), comprometido(), no_time()]

    assert ocupacao(acervo) == 2


def test_o_comprometido_que_esta_em_time_continua_nao_contando():
    # Combinacao que o banco nao deveria permitir (invariante 14), mas que a
    # contagem precisa resolver sem ambiguidade: quem tem treinador nao ocupa
    # lugar, e so isso decide.
    preso = PokemonDoLaboratorio(
        id=uuid4(), treinador_id=TREINADOR, comprometido_entrega_id=ENTREGA
    )

    assert ocupacao([preso]) == 0


def test_a_propriedade_no_viveiro_diz_quem_ocupa_lugar():
    assert guardado().no_viveiro is True
    assert comprometido().no_viveiro is True
    assert no_time().no_viveiro is False


# --- 2. Transbordo: a borda exata (criterio 3) ------------------------------


@pytest.mark.parametrize(
    ("ocupacao_atual", "esperado"),
    [
        (0, False),
        (49, False),
        (50, False),  # cheio nao e transbordado: os cinquenta cabem
        (51, True),
        (65, True),
    ],
)
def test_o_transbordo_comeca_acima_da_capacidade(ocupacao_atual, esperado):
    assert transbordado(ocupacao_atual) is esperado


def test_a_borda_do_transbordo_acompanha_a_constante():
    # Sem esta linha, os numeros do teste de tabela acima virariam mentira
    # silenciosa no dia em que a Fase 9 calibrasse CAPACIDADE_VIVEIRO.
    assert balance.CAPACIDADE_VIVEIRO == 50
    assert transbordado(balance.CAPACIDADE_VIVEIRO) is False
    assert transbordado(balance.CAPACIDADE_VIVEIRO + 1) is True


@pytest.mark.parametrize(
    ("ocupacao_atual", "faltando"),
    [
        (0, 0),
        (49, 0),
        (50, 0),
        (51, 1),
        (52, 2),
        (65, 15),
    ],
)
def test_lugares_faltando_conta_so_o_excedente(ocupacao_atual, faltando):
    assert lugares_faltando(ocupacao_atual) == faltando


def test_lugares_faltando_nunca_e_negativo():
    # Propriedade: lugar vago nao e lugar faltando. Devolver a sobra aqui
    # faria a tela anunciar "faltam -7 lugares".
    assert all(lugares_faltando(n) >= 0 for n in range(0, balance.CAPACIDADE_VIVEIRO * 2))


def test_ocupacao_negativa_e_recusada():
    with pytest.raises(OcupacaoInvalida):
        transbordado(-1)
    with pytest.raises(OcupacaoInvalida):
        lugares_faltando(-1)


# --- 3. O estado que a tela do viveiro le (criterio 1) ----------------------


def test_o_estado_do_viveiro_reune_os_quatro_numeros():
    estado = estado_do_viveiro(52)

    assert estado.capacidade == balance.CAPACIDADE_VIVEIRO
    assert estado.ocupacao == 52
    assert estado.transbordado is True
    assert estado.lugares_faltando == 2


def test_o_estado_do_viveiro_cheio_nao_acusa_transbordo():
    estado = estado_do_viveiro(balance.CAPACIDADE_VIVEIRO)

    assert estado.transbordado is False
    assert estado.lugares_faltando == 0


def test_o_estado_do_viveiro_e_deterministico():
    # Artigo III: mesma entrada, mesma saida, sempre. Sem relogio nem sorteio
    # no caminho, a igualdade das dataclasses frozen basta como prova.
    assert estado_do_viveiro(52) == estado_do_viveiro(52)
    assert estado_do_viveiro(3) == estado_do_viveiro(3)


# --- 4. A guarda do despacho (criterio 4) -----------------------------------


@pytest.mark.parametrize("ocupacao_atual", [0, 1, 49, 50])
def test_o_despacho_passa_enquanto_o_viveiro_cabe(ocupacao_atual):
    assert exigir_espaco_para_despachar(ocupacao_atual) is None


def test_o_despacho_e_recusado_com_o_viveiro_transbordado():
    with pytest.raises(ViveiroTransbordado) as erro:
        exigir_espaco_para_despachar(53)

    assert erro.value.codigo == "VIVEIRO_TRANSBORDADO"
    assert erro.value.detalhes["lugares_faltando"] == 3
    assert erro.value.detalhes["ocupacao"] == 53
    assert erro.value.detalhes["capacidade"] == balance.CAPACIDADE_VIVEIRO


def test_a_recusa_do_despacho_diz_quantos_lugares_faltam():
    # "O viveiro esta cheio" nao informa se o professor solta um Pokemon ou
    # doze; a mensagem precisa carregar o numero (criterio 4).
    with pytest.raises(ViveiroTransbordado) as erro:
        exigir_espaco_para_despachar(62)

    assert "12" in str(erro.value)


# --- 5. A guarda nao escapa para os caminhos de saida (criterio 5) ----------
#
# O maior risco da fase, nomeado no plano da spec 008: uma recusa a mais em
# reclamar, aceitar, concluir ou soltar prende o professor sem saida, e o
# sintoma e um jogador travado sem entender por que — nao um erro no log.
# Nenhum teste de comportamento pega isso, porque o defeito e uma chamada que
# NAO deveria existir. Entao o teste le o codigo.

APP_DIR = Path(__file__).resolve().parent.parent / "app"
NOME_DA_GUARDA = "exigir_espaco_para_despachar"

# Onde a guarda pode ser citada: a propria definicao e o caminho do despacho
# de expedicao. Qualquer outro arquivo que a chame esta fechando uma saida.
ARQUIVOS_AUTORIZADOS = ("viveiro.py", "expedicoes.py", "expedition.py")


def _arquivos_que_citam_a_guarda() -> list[Path]:
    return [
        arquivo
        for arquivo in sorted(APP_DIR.rglob("*.py"))
        if NOME_DA_GUARDA in arquivo.read_text(encoding="utf-8")
    ]


def test_a_guarda_do_transbordo_so_aparece_no_caminho_do_despacho():
    intrusos = [
        str(arquivo.relative_to(APP_DIR))
        for arquivo in _arquivos_que_citam_a_guarda()
        if arquivo.name not in ARQUIVOS_AUTORIZADOS
    ]

    assert not intrusos, (
        "A guarda de capacidade escapou para um caminho que nao e o despacho: "
        + "; ".join(intrusos)
        + ". Reclamar relatorio, aceitar entrega, concluir entrega e soltar sao as SAIDAS do "
        "transbordo (regra 4 da spec 008) e nao podem consultar a capacidade."
    )


def test_nenhum_outro_modulo_do_dominio_chama_a_guarda():
    # Dentro de game/ a guarda e chamada por ninguem: quem a chama e o servico
    # de despacho. Em particular, `soltar.py` nao pode toca-la.
    game_dir = APP_DIR / "game"
    infratores: list[str] = []
    for arquivo in sorted(game_dir.rglob("*.py")):
        if arquivo.name == "viveiro.py":
            continue
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Call):
                alvo = no.func
                nome = getattr(alvo, "id", None) or getattr(alvo, "attr", None)
                if nome == NOME_DA_GUARDA:
                    infratores.append(arquivo.name)

    assert not infratores, "Artigo VI e regra 4 da spec 008: " + "; ".join(infratores)
