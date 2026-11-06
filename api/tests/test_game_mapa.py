"""Mapa de Kanto: alcance, rotas otimas e duracao estimada (spec 005, SDD 4.4).

O grafo de Kanto abaixo e transcrito de `data/seed/locations.json` a mao, e nao
lido do arquivo: um teste de dominio que le o seed passa a testar duas coisas
ao mesmo tempo e deixa de dizer qual das duas quebrou. A integridade do seed e
de `test_seed_integridade.py`.

Os tempos da tabela de duracao foram calculados a mao a partir da formula da
secao 4.4 do SDD, e conferem com o exemplo que o proprio SDD publica: Mt. Moon
partindo de Pallet Town, 55 minutos.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Collection
from dataclasses import FrozenInstanceError

import pytest

from app.game import balance
from app.game.mapa import (
    DestinoForaDeAlcance,
    EstadoDoLocal,
    GrafoDeLocais,
    GrafoInvalido,
    LocalDesconhecido,
    LocalNoGrafo,
    ParametroDeDuracaoInvalido,
    alcancaveis,
    duracao_estimada,
    estado_de,
    exigir_destino_alcancavel,
    montar_grafo,
    proximo_passo,
    rota_ate,
    rotas_otimas,
    visao_do_mapa,
)
from app.game.trainers import NivelDeTreinadorInvalido

# --- O mapa da v1 -----------------------------------------------------------

CIDADE = 3
ROTA = 4
MASMORRA = 8

KANTO = montar_grafo(
    [
        LocalNoGrafo("pallet-town", CIDADE, 2, ("route-1",)),
        LocalNoGrafo("route-1", ROTA, 3, ("pallet-town", "viridian-city")),
        LocalNoGrafo("viridian-city", CIDADE, 3, ("route-1", "route-2", "route-22")),
        LocalNoGrafo("route-22", ROTA, 4, ("viridian-city",)),
        LocalNoGrafo("route-2", ROTA, 4, ("viridian-city", "viridian-forest")),
        LocalNoGrafo("viridian-forest", MASMORRA, 6, ("route-2", "pewter-city")),
        LocalNoGrafo("pewter-city", CIDADE, 3, ("viridian-forest", "route-3")),
        LocalNoGrafo("route-3", ROTA, 5, ("pewter-city", "mt-moon")),
        LocalNoGrafo("mt-moon", MASMORRA, 7, ("route-3", "cerulean-city")),
        LocalNoGrafo("cerulean-city", CIDADE, 4, ("mt-moon",)),
    ]
)

SO_PALLET = ("pallet-town",)


# --- Dijkstra x busca em largura --------------------------------------------


def _caminho_com_menos_arestas(
    grafo: GrafoDeLocais, visitados: Collection[str], destino_id: str
) -> tuple[str, ...]:
    """Busca em largura, escrita aqui so para provar que ela responde OUTRA coisa.

    E a implementacao ingenua que a spec 005 proibe: ela minimiza o numero de
    locais atravessados, e nao os minutos gastos atravessando-os.
    """
    fila: deque[tuple[str, ...]] = deque((local_id,) for local_id in sorted(visitados))
    vistos = set(visitados)
    while fila:
        caminho = fila.popleft()
        if caminho[-1] == destino_id:
            return caminho
        for vizinho_id in grafo.local(caminho[-1]).vizinhos:
            if vizinho_id not in vistos:
                vistos.add(vizinho_id)
                fila.append((*caminho, vizinho_id))
    return ()


# Atalho por duas masmorras (8 + 8 + 3 = 19 minutos, tres arestas) contra
# desvio por tres cidades (3 + 3 + 3 + 3 = 12 minutos, quatro arestas). A busca
# em largura escolhe o atalho porque conta arestas; Dijkstra escolhe o desvio
# porque conta minutos. O mapa linear de dez nos da v1 nao exibe essa
# diferenca, e e justamente por isso que ela precisa de um grafo proprio.
GRAFO_COM_ATALHO_CARO = montar_grafo(
    [
        LocalNoGrafo("casa", CIDADE, 1, ("masmorra-1", "cidade-1")),
        LocalNoGrafo("masmorra-1", MASMORRA, 1, ("casa", "masmorra-2")),
        LocalNoGrafo("masmorra-2", MASMORRA, 1, ("masmorra-1", "alvo")),
        LocalNoGrafo("cidade-1", CIDADE, 1, ("casa", "cidade-2")),
        LocalNoGrafo("cidade-2", CIDADE, 1, ("cidade-1", "cidade-3")),
        LocalNoGrafo("cidade-3", CIDADE, 1, ("cidade-2", "alvo")),
        LocalNoGrafo("alvo", CIDADE, 1, ("masmorra-2", "cidade-3")),
    ]
)


def test_a_rota_otima_e_a_mais_rapida_e_nao_a_de_menos_arestas():
    rota = rotas_otimas(GRAFO_COM_ATALHO_CARO, ("casa",))["alvo"]

    assert rota.caminho == ("casa", "cidade-1", "cidade-2", "cidade-3", "alvo")
    assert rota.custo_viagem_minutos == CIDADE * 4

    por_arestas = _caminho_com_menos_arestas(GRAFO_COM_ATALHO_CARO, ("casa",), "alvo")
    assert por_arestas == ("casa", "masmorra-1", "masmorra-2", "alvo")
    assert len(por_arestas) < len(rota.caminho)
    assert rota.custo_viagem_minutos < MASMORRA + MASMORRA + CIDADE


def test_o_proximo_passo_segue_a_rota_mais_rapida_e_nao_a_mais_curta():
    assert proximo_passo(GRAFO_COM_ATALHO_CARO, ("casa",), "alvo") == "cidade-1"


# --- Alcance (criterios 1, 2, 5) --------------------------------------------


def test_de_pallet_so_route_1_esta_ao_alcance():
    assert alcancaveis(KANTO, SO_PALLET) == ("route-1",)


def test_de_pallet_as_demais_estao_fora_de_alcance():
    ao_alcance = alcancaveis(KANTO, SO_PALLET)
    estados = {local_id: estado_de(local_id, SO_PALLET, ao_alcance) for local_id in KANTO.ids}

    assert estados["pallet-town"] is EstadoDoLocal.VISITADO
    assert estados["route-1"] is EstadoDoLocal.ALCANCAVEL
    fora = [
        local_id for local_id, estado in estados.items() if estado is EstadoDoLocal.FORA_DE_ALCANCE
    ]
    assert sorted(fora) == sorted(set(KANTO.ids) - {"pallet-town", "route-1"})
    assert estados["cerulean-city"] is EstadoDoLocal.FORA_DE_ALCANCE


def test_visitar_route_1_abre_viridian_city():
    antes = alcancaveis(KANTO, SO_PALLET)
    depois = alcancaveis(KANTO, ("pallet-town", "route-1"))

    assert "viridian-city" not in antes
    assert depois == ("viridian-city",)


def test_um_local_visitado_nao_aparece_entre_os_alcancaveis():
    visitados = ("pallet-town", "route-1", "viridian-city")
    assert set(alcancaveis(KANTO, visitados)).isdisjoint(visitados)
    assert alcancaveis(KANTO, visitados) == ("route-2", "route-22")


def test_visitado_vence_alcancavel_quando_o_local_e_as_duas_coisas():
    assert estado_de("route-1", ("route-1",), ("route-1",)) is EstadoDoLocal.VISITADO


# --- Rotas otimas (criterios 4, 6, 7) ---------------------------------------


def test_cada_rota_parte_de_um_visitado_e_termina_no_destino():
    visitados = ("pallet-town", "route-1")
    for destino_id, rota in rotas_otimas(KANTO, visitados).items():
        assert rota.caminho[0] in visitados
        assert rota.caminho[0] == rota.origem_id
        assert rota.caminho[-1] == destino_id == rota.destino_id
        assert rota.custo_viagem_minutos >= 0


def test_local_visitado_continua_sendo_destino_com_viagem_zero():
    # Regra 4 da spec 005: repetir e permitido, e quem repete ja esta la — a
    # viagem custa zero mesmo havendo outro visitado vizinho.
    rotas = rotas_otimas(KANTO, ("pallet-town", "route-1"))

    assert rotas["route-1"].custo_viagem_minutos == 0
    assert rotas["route-1"].origem_id == "route-1"
    assert rotas["route-1"].caminho == ("route-1",)
    assert rotas["pallet-town"].custo_viagem_minutos == 0


def test_visitar_viridian_city_encurta_a_viagem_ate_route_2():
    de_pallet = rotas_otimas(KANTO, SO_PALLET)["route-2"]
    de_viridian = rotas_otimas(KANTO, ("pallet-town", "route-1", "viridian-city"))["route-2"]

    assert de_pallet.origem_id == "pallet-town"
    assert de_pallet.custo_viagem_minutos == ROTA + CIDADE + ROTA  # 11
    assert de_viridian.origem_id == "viridian-city"
    assert de_viridian.custo_viagem_minutos == ROTA  # 4
    assert de_viridian.custo_viagem_minutos < de_pallet.custo_viagem_minutos


def test_a_ida_a_mt_moon_encurta_conforme_o_mapa_abre():
    # O exemplo do SDD 4.4: 34 minutos de viagem partindo de Pallet, 8
    # partindo de Route 3.
    assert rotas_otimas(KANTO, SO_PALLET)["mt-moon"].custo_viagem_minutos == 34
    assert rotas_otimas(KANTO, ("route-3",))["mt-moon"].custo_viagem_minutos == MASMORRA


def test_a_rota_de_um_destino_so_e_a_mesma_do_mapa_inteiro():
    assert rota_ate(KANTO, SO_PALLET, "mt-moon") == rotas_otimas(KANTO, SO_PALLET)["mt-moon"]


# --- Proximo passo (criterio 3) ---------------------------------------------


def test_proximo_passo_de_pewter_city_e_route_1_e_nao_o_caminho_todo():
    passo = proximo_passo(KANTO, SO_PALLET, "pewter-city")
    caminho = rotas_otimas(KANTO, SO_PALLET)["pewter-city"].caminho

    assert passo == "route-1"
    assert len(caminho) > 2  # o caminho inteiro existe; a resposta util e so o primeiro no


def test_local_ao_alcance_ou_visitado_nao_tem_proximo_passo():
    assert proximo_passo(KANTO, SO_PALLET, "route-1") is None
    assert proximo_passo(KANTO, SO_PALLET, "pallet-town") is None


def test_proximo_passo_de_local_inexistente_e_recusado():
    with pytest.raises(LocalDesconhecido):
        proximo_passo(KANTO, SO_PALLET, "saffron-city")


# --- Duracao estimada (SDD 4.4) ---------------------------------------------

# Viagem e exploracao de cada local partindo so de Pallet Town, somadas a mao:
#   duracao = viagem + encontros_base * MINUTOS_POR_ENCONTRO
# A lista esta na ordem de proximidade, que e a mesma que o mapa devolve.
TABELA_DESDE_PALLET = [
    ("pallet-town", 0, 6),  # 0 + 2*3
    ("route-1", 4, 13),  # 4 + 3*3
    ("viridian-city", 7, 16),  # 4+3 + 3*3
    ("route-2", 11, 23),  # 4+3+4 + 4*3
    ("route-22", 11, 23),  # 4+3+4 + 4*3
    ("viridian-forest", 19, 37),  # 4+3+4+8 + 6*3
    ("pewter-city", 22, 31),  # +3 + 3*3
    ("route-3", 26, 41),  # +4 + 5*3
    ("mt-moon", 34, 55),  # +8 + 7*3  (o exemplo publicado no SDD)
    ("cerulean-city", 37, 49),  # +3 + 4*3
]


@pytest.mark.parametrize(("local_id", "viagem", "duracao"), TABELA_DESDE_PALLET)
def test_tabela_de_duracao_desde_pallet(local_id, viagem, duracao):
    rota = rotas_otimas(KANTO, SO_PALLET)[local_id]
    assert rota.custo_viagem_minutos == viagem
    assert (
        duracao_estimada(
            custo_viagem_minutos=rota.custo_viagem_minutos,
            encontros_base=KANTO.local(local_id).encontros_base,
        )
        == duracao
    )


@pytest.mark.parametrize(
    ("nivel", "esperado"),
    [
        (1, 54),  # 55 * 0.98 = 53.9
        (10, 44),  # 55 * 0.80 = 44
        (20, 33),  # 55 * 0.60 = 33
        (50, 33),  # reducao travada em REDUCAO_MAXIMA_TREINADOR
        (100, 33),
    ],
)
def test_o_treinador_experiente_encurta_a_ida(nivel, esperado):
    assert duracao_estimada(custo_viagem_minutos=34, encontros_base=7, nivel_treinador=nivel) == (
        esperado
    )


@pytest.mark.parametrize(
    ("bonus", "esperado"),
    [
        (0.0, 55),
        (0.2, 44),  # 55 * 0.80
        (0.25, 41),  # 55 * 0.75 = 41.25
        (0.9, 41),  # cortado em BONUS_ITENS_MAXIMO
    ],
)
def test_a_carga_de_apoio_encurta_a_ida_ate_o_teto(bonus, esperado):
    assert duracao_estimada(custo_viagem_minutos=34, encontros_base=7, bonus_itens=bonus) == (
        esperado
    )


def test_a_escala_de_tempo_multiplica_a_duracao():
    # Multiplica, nao divide: o ADR-004 e o .env.example sempre disseram que
    # 0.01 encolhe vinte minutos para doze segundos. O SDD dizia "divide" ate a
    # Fase 5, e seguir o texto deixava a expedicao cem vezes mais LONGA em
    # desenvolvimento — o documento e que foi corrigido.
    assert duracao_estimada(custo_viagem_minutos=34, encontros_base=7) == 55
    assert duracao_estimada(custo_viagem_minutos=34, encontros_base=7, escala=0.5) == 28
    assert duracao_estimada(custo_viagem_minutos=34, encontros_base=7, escala=2.0) == 110


def test_a_duracao_nunca_e_zero():
    # Com a escala acelerada do ADR-004 a conta cai abaixo de um minuto, e uma
    # expedicao de zero minuto terminaria no instante em que parte.
    assert duracao_estimada(custo_viagem_minutos=0, encontros_base=0) == (
        balance.DURACAO_MINIMA_MINUTOS
    )
    assert duracao_estimada(custo_viagem_minutos=34, encontros_base=7, escala=0.001) == (
        balance.DURACAO_MINIMA_MINUTOS
    )


def test_os_descontos_se_combinam():
    # 55 * 0.80 (nivel 10) * 0.80 (bonus 0.2) = 35.2
    assert (
        duracao_estimada(
            custo_viagem_minutos=34, encontros_base=7, nivel_treinador=10, bonus_itens=0.2
        )
        == 35
    )


def test_o_tempo_de_exploracao_vem_do_destino_e_nao_da_viagem():
    perto_e_rico = duracao_estimada(custo_viagem_minutos=0, encontros_base=7)
    longe_e_pobre = duracao_estimada(custo_viagem_minutos=20, encontros_base=1)

    assert perto_e_rico == 7 * balance.MINUTOS_POR_ENCONTRO
    assert longe_e_pobre == 20 + balance.MINUTOS_POR_ENCONTRO


@pytest.mark.parametrize(
    "argumentos",
    [
        {"custo_viagem_minutos": -1, "encontros_base": 2},
        {"custo_viagem_minutos": 4, "encontros_base": -2},
        {"custo_viagem_minutos": 4, "encontros_base": 2, "bonus_itens": -0.1},
        {"custo_viagem_minutos": 4, "encontros_base": 2, "escala": 0.0},
        {"custo_viagem_minutos": 4, "encontros_base": 2, "escala": -1.0},
    ],
)
def test_parametros_impossiveis_de_duracao_sao_recusados(argumentos):
    with pytest.raises(ParametroDeDuracaoInvalido):
        duracao_estimada(**argumentos)


def test_nivel_de_treinador_fora_da_faixa_e_recusado():
    with pytest.raises(NivelDeTreinadorInvalido):
        duracao_estimada(custo_viagem_minutos=4, encontros_base=2, nivel_treinador=0)
    with pytest.raises(NivelDeTreinadorInvalido):
        duracao_estimada(
            custo_viagem_minutos=4, encontros_base=2, nivel_treinador=balance.NIVEL_MAXIMO + 1
        )


# --- Invariante 6 do SDD 3.3 ------------------------------------------------


def test_destino_alcancavel_devolve_a_rota():
    rota = exigir_destino_alcancavel(KANTO, SO_PALLET, "route-1")
    assert rota.origem_id == "pallet-town"
    assert rota.custo_viagem_minutos == ROTA


def test_destino_visitado_e_aceito_com_viagem_zero():
    rota = exigir_destino_alcancavel(KANTO, SO_PALLET, "pallet-town")
    assert rota.custo_viagem_minutos == 0


def test_destino_fora_de_alcance_e_recusado_dizendo_o_que_falta():
    with pytest.raises(DestinoForaDeAlcance) as recusa:
        exigir_destino_alcancavel(KANTO, SO_PALLET, "cerulean-city")

    assert recusa.value.detalhes["proximo_passo_id"] == "route-1"
    assert "route-1" in str(recusa.value)


def test_destino_inexistente_e_recusado_como_desconhecido():
    with pytest.raises(LocalDesconhecido):
        exigir_destino_alcancavel(KANTO, SO_PALLET, "saffron-city")


# --- Estados degenerados ----------------------------------------------------


GRAFO_COM_ILHA = montar_grafo(
    [
        LocalNoGrafo("casa", CIDADE, 1, ("vizinha",)),
        LocalNoGrafo("vizinha", CIDADE, 1, ("casa",)),
        LocalNoGrafo("ilha", CIDADE, 1, ()),
    ]
)


def test_local_isolado_fica_fora_de_alcance_sem_proximo_passo():
    assert "ilha" not in rotas_otimas(GRAFO_COM_ILHA, ("casa",))
    assert proximo_passo(GRAFO_COM_ILHA, ("casa",), "ilha") is None
    assert estado_de("ilha", ("casa",), alcancaveis(GRAFO_COM_ILHA, ("casa",))) is (
        EstadoDoLocal.FORA_DE_ALCANCE
    )


def test_sem_nenhum_visitado_o_mapa_responde_vazio_em_vez_de_explodir():
    # Nao acontece em jogo — Pallet Town nasce visitada —, mas a leitura do
    # mapa nao pode depender disso para nao derrubar a tela.
    assert alcancaveis(KANTO, ()) == ()
    assert rotas_otimas(KANTO, ()) == {}
    assert proximo_passo(KANTO, (), "route-1") is None
    assert all(linha.estado is EstadoDoLocal.FORA_DE_ALCANCE for linha in visao_do_mapa(KANTO, ()))


def test_visitado_que_nao_existe_no_grafo_e_ignorado():
    rotas = rotas_otimas(KANTO, ("pallet-town", "saffron-city"))
    assert "saffron-city" not in rotas
    assert rotas["route-1"].origem_id == "pallet-town"


GRAFO_ASSIMETRICO = montar_grafo(
    [
        LocalNoGrafo("casa", CIDADE, 1, ("beco",)),
        LocalNoGrafo("beco", ROTA, 1, ()),  # nao aponta de volta para casa
    ]
)


def test_vizinhanca_assimetrica_nao_impede_a_busca_de_terminar():
    # Ha teste desde a Fase 1 garantindo que o seed e reciproco; a busca nao
    # pode depender disso para parar.
    assert rotas_otimas(GRAFO_ASSIMETRICO, ("casa",))["beco"].custo_viagem_minutos == ROTA
    assert "casa" not in rotas_otimas(GRAFO_ASSIMETRICO, ("beco",))


# --- Grafo invalido ---------------------------------------------------------


def test_local_repetido_no_grafo_e_recusado():
    with pytest.raises(GrafoInvalido):
        montar_grafo([LocalNoGrafo("casa", CIDADE, 1), LocalNoGrafo("casa", ROTA, 2)])


def test_custo_de_travessia_negativo_e_recusado():
    with pytest.raises(GrafoInvalido):
        montar_grafo([LocalNoGrafo("casa", -1, 1)])


def test_numero_de_encontros_negativo_e_recusado():
    with pytest.raises(GrafoInvalido):
        montar_grafo([LocalNoGrafo("casa", CIDADE, -1)])


def test_vizinho_inexistente_e_recusado():
    with pytest.raises(GrafoInvalido):
        montar_grafo([LocalNoGrafo("casa", CIDADE, 1, ("lugar-nenhum",))])


def test_o_grafo_e_imutavel():
    with pytest.raises(FrozenInstanceError):
        KANTO.locais = ()  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        KANTO.locais[0].id = "outro"  # type: ignore[misc]


# --- Determinismo (Artigo III) ----------------------------------------------

# Dois caminhos de custo identico ate o alvo: a escolha precisa ser sempre a
# mesma, e nao pode depender da ordem em que os locais ou os visitados chegaram.
GRAFO_COM_EMPATE = montar_grafo(
    [
        LocalNoGrafo("casa", CIDADE, 1, ("norte", "sul")),
        LocalNoGrafo("norte", ROTA, 1, ("casa", "alvo")),
        LocalNoGrafo("sul", ROTA, 1, ("casa", "alvo")),
        LocalNoGrafo("alvo", CIDADE, 1, ("norte", "sul")),
    ]
)

GRAFO_COM_EMPATE_INVERTIDO = montar_grafo(reversed(GRAFO_COM_EMPATE.locais))


def test_a_mesma_entrada_produz_a_mesma_saida():
    visitados = ("pallet-town", "route-1", "viridian-city")
    assert rotas_otimas(KANTO, visitados) == rotas_otimas(KANTO, visitados)
    assert alcancaveis(KANTO, visitados) == alcancaveis(KANTO, visitados)
    assert visao_do_mapa(KANTO, visitados) == visao_do_mapa(KANTO, visitados)


def test_o_desempate_entre_caminhos_iguais_e_estavel():
    escolhido = ("casa", "norte", "alvo")
    assert rotas_otimas(GRAFO_COM_EMPATE, ("casa",))["alvo"].caminho == escolhido
    assert rotas_otimas(GRAFO_COM_EMPATE_INVERTIDO, ("casa",))["alvo"].caminho == escolhido


@pytest.mark.parametrize(
    "visitados",
    [
        ("casa", "norte", "sul"),
        ("sul", "norte", "casa"),
        {"norte", "casa", "sul"},
        frozenset({"sul", "casa", "norte"}),
        ["norte", "sul", "casa"],
    ],
)
def test_a_saida_nao_depende_da_ordem_nem_do_tipo_do_conjunto_de_visitados(visitados):
    rotas = rotas_otimas(GRAFO_COM_EMPATE, visitados)
    assert rotas["alvo"].caminho == ("norte", "alvo")
    assert alcancaveis(GRAFO_COM_EMPATE, visitados) == ("alvo",)


# --- O mapa inteiro ---------------------------------------------------------


def test_o_mapa_mostra_os_dez_locais_do_mais_perto_ao_mais_longe():
    # Regra 1 da spec 005: os dez aparecem sempre. A ordem e a distancia do
    # caminho, inclusive para quem ainda esta fora de alcance — Cerulean City e
    # o fim do mapa, e nao o terceiro item por comecar com C.
    linhas = visao_do_mapa(KANTO, SO_PALLET)

    assert [linha.id for linha in linhas] == [local_id for local_id, _, _ in TABELA_DESDE_PALLET]
    assert len(linhas) == len(KANTO.ids)
    com_duracao = [linha for linha in linhas if linha.duracao_estimada_minutos is not None]
    assert [linha.id for linha in com_duracao] == ["pallet-town", "route-1"]


def test_o_mapa_traz_duracao_para_quem_esta_ao_alcance_e_falta_para_o_resto():
    por_id = {linha.id: linha for linha in visao_do_mapa(KANTO, SO_PALLET)}

    route_1 = por_id["route-1"]
    assert route_1.estado is EstadoDoLocal.ALCANCAVEL
    assert route_1.origem_id == "pallet-town"
    assert route_1.duracao_estimada_minutos == 13
    assert route_1.proximo_passo_id is None

    pewter = por_id["pewter-city"]
    assert pewter.estado is EstadoDoLocal.FORA_DE_ALCANCE
    assert pewter.origem_id is None
    assert pewter.duracao_estimada_minutos is None
    assert pewter.proximo_passo_id == "route-1"


def test_o_mapa_e_o_detalhe_concordam_em_estado_e_duracao():
    visitados = ("pallet-town", "route-1")
    rotas = rotas_otimas(KANTO, visitados)
    ao_alcance = alcancaveis(KANTO, visitados)

    for linha in visao_do_mapa(KANTO, visitados, nivel_treinador=10):
        assert linha.estado is estado_de(linha.id, visitados, ao_alcance)
        if linha.estado is EstadoDoLocal.FORA_DE_ALCANCE:
            assert linha.proximo_passo_id == proximo_passo(KANTO, visitados, linha.id)
            continue
        assert linha.custo_viagem_minutos == rotas[linha.id].custo_viagem_minutos
        assert linha.duracao_estimada_minutos == duracao_estimada(
            custo_viagem_minutos=rotas[linha.id].custo_viagem_minutos,
            encontros_base=KANTO.local(linha.id).encontros_base,
            nivel_treinador=10,
        )


def test_abrir_o_mapa_nunca_alonga_nenhuma_ida():
    # A promessa do SDD 4.4: desbloquear encurta de verdade. Nenhuma duracao
    # pode subir conforme o professor progride.
    progresso = ["pallet-town", "route-1", "viridian-city", "route-2", "viridian-forest"]
    anterior: dict[str, int] = {}
    for quantos in range(1, len(progresso) + 1):
        atual = {
            linha.id: linha.duracao_estimada_minutos
            for linha in visao_do_mapa(KANTO, progresso[:quantos])
            if linha.duracao_estimada_minutos is not None
        }
        for local_id, duracao in anterior.items():
            assert atual[local_id] <= duracao
        anterior = atual


def test_toda_duracao_do_mapa_respeita_o_piso():
    for linha in visao_do_mapa(KANTO, SO_PALLET, escala=1000.0):
        if linha.duracao_estimada_minutos is not None:
            assert linha.duracao_estimada_minutos >= balance.DURACAO_MINIMA_MINUTOS
