"""Central de Entregas: banda de raridade, prazo da oferta e recompensa.

Cobre os criterios 13 a 22 e 27 da spec 008 no dominio puro, sem banco.

O teste que mais importa aqui e a tabela de `piso_de_raridade`: ela prova o
SENTIDO da escala de `taxa_captura`, que anda ao contrario da intuicao — 3 e
Mewtwo e 255 e Caterpie, logo taxa alta e especie COMUM. Escrever a
desigualdade invertida faz o laboratorio nivel 1 encomendar Mewtwo, e nenhum
outro teste pegaria isso: a geracao continuaria funcionando, com os pedidos
errados.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from app.game import balance, mapa
from app.game.delivery import (
    CatalogoDeEntregaInvalido,
    CidadeDeDestino,
    EspecieParaEntrega,
    EstadoObservadoEntrega,
    ParametroDeEntregaInvalido,
    PokemonEntregue,
    PokemonNaoAtendeAoPedido,
    PrazoDeEntregaAusente,
    RequisitoDoPedido,
    SemCidadeDeDestino,
    SemEspecieCandidata,
    StatusEntrega,
    banda_de_raridade,
    candidatas_do_nivel,
    duracao_da_entrega,
    duracao_da_oferta,
    estado_observado_entrega,
    exigir_pokemon_que_atendem,
    expiracao_da_oferta,
    gerar_pedido,
    gerar_pedidos,
    locais_ao_alcance,
    moedas_por_pokemon,
    piso_de_raridade,
    proxima_regeracao,
    recompensa_da_entrega,
    segundos_para_expirar,
    segundos_para_regerar,
    teto_de_quantidade,
    vagas_para_repor,
)
from app.game.erros import TaxaDeCapturaInvalida
from app.game.expedition import RelogioSemFuso
from app.game.laboratorio import NivelDeLaboratorioInvalido
from tests.geradores_falsos import GeradorRoteirizado, GeradorSemeado

RAIZ = Path(__file__).resolve().parent.parent.parent
DIR_SEED = RAIZ / "data" / "seed"

AGORA = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)

# Escala de desenvolvimento do .env.example (ADR-004). Nao e calibragem: e
# ambiente, e por isso chega ao dominio como parametro.
ESCALA_DE_DESENVOLVIMENTO = 0.01


# --- Catalogo do seed, que e o dado de verdade (Artigo V) -------------------


def _ler(nome: str) -> Any:
    return json.loads((DIR_SEED / nome).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def especies_do_seed() -> tuple[EspecieParaEntrega, ...]:
    """As 151 especies, com os locais em que cada uma aparece."""
    encontros = _ler("encounters.json")
    locais_por_especie: dict[int, list[str]] = {}
    for local_id, linhas in encontros.items():
        for linha in linhas:
            locais_por_especie.setdefault(linha["especie_id"], []).append(local_id)
    return tuple(
        EspecieParaEntrega(
            id=especie["id"],
            nome=especie["nome"],
            taxa_captura=especie["taxa_captura"],
            locais_ids=tuple(sorted(locais_por_especie.get(especie["id"], ()))),
        )
        for especie in _ler("species.json")
    )


@pytest.fixture(scope="module")
def grafo_de_kanto() -> mapa.GrafoDeLocais:
    return mapa.montar_grafo(
        mapa.LocalNoGrafo(
            id=local["id"],
            custo_travessia_minutos=local["custo_travessia_minutos"],
            encontros_base=local["encontros_base"],
            vizinhos=tuple(local["vizinhos"]),
        )
        for local in _ler("locations.json")
    )


@pytest.fixture(scope="module")
def cidades_do_seed() -> dict[str, CidadeDeDestino]:
    return {
        local["id"]: CidadeDeDestino(id=local["id"], nome=local["nome"])
        for local in _ler("locations.json")
        if local["tipo"] == "CIDADE"
    }


# --- Catalogos de mao, para as tabelas --------------------------------------

PIDGEY = EspecieParaEntrega(id=16, nome="Pidgey", taxa_captura=255, locais_ids=("route-1",))
RATTATA = EspecieParaEntrega(id=19, nome="Rattata", taxa_captura=255, locais_ids=("route-1",))
PIKACHU = EspecieParaEntrega(id=25, nome="Pikachu", taxa_captura=190, locais_ids=("route-1",))
DRAGONITE = EspecieParaEntrega(id=149, nome="Dragonite", taxa_captura=45, locais_ids=("route-1",))
MEWTWO_LONGE = EspecieParaEntrega(id=150, nome="Mewtwo", taxa_captura=3, locais_ids=("cerulean",))

VIRIDIAN = CidadeDeDestino(id="viridian-city", nome="Viridian City")
PALLET = CidadeDeDestino(id="pallet-town", nome="Pallet Town")


# --- A banda de raridade: o SENTIDO da escala -------------------------------

# taxa_captura vai de 3 (Mewtwo, raro) a 255 (Caterpie, comum), mediana 75.
# TAXA ALTA E ESPECIE COMUM, entao o piso DESCE conforme o nivel sobe.
TABELA_DO_PISO = [
    (1, 255),  # so o topo da escala: Pidgey, Rattata, Caterpie
    (2, 227),
    (3, 199),  # ja alcanca Pikachu e Psyduck (190)
    (4, 171),
    (5, 143),
    (6, 115),
    (7, 87),
    (8, 59),  # passou da mediana da escala (75)
    (9, 31),
    (10, 3),  # banda aberta ate Mewtwo
    (11, 3),
    (99, 3),
]


@pytest.mark.parametrize(("nivel", "piso_esperado"), TABELA_DO_PISO)
def test_piso_de_raridade_desce_conforme_o_nivel_sobe(nivel, piso_esperado):
    assert piso_de_raridade(nivel) == piso_esperado


def test_a_banda_do_nivel_1_e_so_o_topo_da_escala():
    piso, teto = banda_de_raridade(1)

    assert teto == balance.TAXA_CAPTURA_MAXIMA
    assert piso == balance.TAXA_CAPTURA_MAXIMA


def test_a_banda_do_nivel_alto_chega_ao_fundo_da_escala():
    piso, _ = banda_de_raridade(balance.NIVEL_LABORATORIO_BANDA_TOTAL)

    assert piso == balance.TAXA_CAPTURA_MINIMA


@pytest.mark.parametrize("nivel", range(1, 20))
def test_o_piso_nunca_sobe_quando_o_nivel_sobe(nivel):
    assert piso_de_raridade(nivel + 1) <= piso_de_raridade(nivel)


def test_nivel_de_laboratorio_invalido_e_recusado():
    with pytest.raises(NivelDeLaboratorioInvalido):
        piso_de_raridade(0)


# --- Candidatas: banda INTERSECAO alcance ------------------------------------


def test_nivel_1_nao_alcanca_especie_rara():
    candidatas = candidatas_do_nivel(1, (PIDGEY, PIKACHU, DRAGONITE), {"route-1"})

    assert candidatas == (PIDGEY,)


def test_nivel_alto_alcanca_a_especie_rara_que_o_nivel_1_nao_alcancava():
    candidatas = candidatas_do_nivel(5, (PIDGEY, PIKACHU, DRAGONITE), {"route-1"})

    assert [especie.nome for especie in candidatas] == ["Pidgey", "Pikachu"]


def test_especie_fora_de_local_alcancavel_nao_e_candidata():
    candidatas = candidatas_do_nivel(
        balance.NIVEL_LABORATORIO_BANDA_TOTAL,
        (PIDGEY, MEWTWO_LONGE),
        {"route-1"},
    )

    assert candidatas == (PIDGEY,)


def test_as_candidatas_saem_em_ordem_canonica_de_especie_id():
    candidatas = candidatas_do_nivel(1, (RATTATA, PIDGEY), {"route-1"})

    assert [especie.id for especie in candidatas] == [16, 19]


def test_catalogo_com_especie_repetida_e_recusado():
    with pytest.raises(CatalogoDeEntregaInvalido):
        candidatas_do_nivel(1, (PIDGEY, PIDGEY), {"route-1"})


def test_taxa_de_captura_fora_da_escala_do_seed_e_recusada():
    impossivel = EspecieParaEntrega(id=1, nome="Bulbasaur", taxa_captura=999)

    with pytest.raises(TaxaDeCapturaInvalida):
        candidatas_do_nivel(1, (impossivel,), {"route-1"})


# --- Intersecao vazia: a resposta deliberada --------------------------------


def test_intersecao_vazia_alarga_a_banda_ate_achar_candidata():
    # Dragonite (45) esta fora da banda do nivel 1 (piso 255), e e a unica
    # especie que vive em local alcancavel. Em vez de devolver lista vazia ou
    # levantar, a banda desce ate alcanca-la.
    candidatas = candidatas_do_nivel(1, (DRAGONITE,), {"route-1"})

    assert candidatas == (DRAGONITE,)


def test_o_alargamento_da_banda_e_deterministico():
    primeira = candidatas_do_nivel(1, (DRAGONITE, MEWTWO_LONGE), {"route-1"})
    segunda = candidatas_do_nivel(1, (MEWTWO_LONGE, DRAGONITE), {"route-1"})

    assert primeira == segunda == (DRAGONITE,)


def test_o_alargamento_para_no_primeiro_nivel_que_acha_candidata():
    # Pikachu (190) entra a partir do piso 199 do nivel 3; Dragonite (45) so
    # entraria no nivel 8. O alargamento para no primeiro nivel util e nao
    # abre a banda inteira de uma vez.
    candidatas = candidatas_do_nivel(1, (PIKACHU, DRAGONITE), {"route-1"})

    assert candidatas == (PIKACHU,)


def test_sem_nenhuma_especie_em_local_alcancavel_o_dominio_levanta():
    with pytest.raises(SemEspecieCandidata):
        candidatas_do_nivel(1, (MEWTWO_LONGE,), {"route-1"})


# --- Alcance: a mesma nocao de exigir_destino_alcancavel --------------------


def test_o_alcance_e_o_visitado_mais_o_vizinho_do_visitado(grafo_de_kanto):
    assert locais_ao_alcance(grafo_de_kanto, {"pallet-town"}) == ("pallet-town", "route-1")


def test_o_alcance_cresce_junto_com_os_locais_desbloqueados(grafo_de_kanto):
    alcance = locais_ao_alcance(grafo_de_kanto, {"pallet-town", "route-1"})

    assert alcance == ("pallet-town", "route-1", "viridian-city")


def test_o_alcance_nao_depende_da_ordem_dos_visitados(grafo_de_kanto):
    uma = locais_ao_alcance(grafo_de_kanto, ["route-1", "pallet-town"])
    outra = locais_ao_alcance(grafo_de_kanto, ("pallet-town", "route-1"))

    assert uma == outra


def test_nenhuma_especie_pedida_vive_fora_do_alcance(
    especies_do_seed, grafo_de_kanto, cidades_do_seed
):
    # Criterio 16 da spec 008, com o mapa e o seed de verdade.
    visitados = {"pallet-town", "route-1", "viridian-city"}
    alcance = set(locais_ao_alcance(grafo_de_kanto, visitados))
    por_id = {especie.id: especie for especie in especies_do_seed}

    for semente in range(40):
        pedidos = gerar_pedidos(
            balance.ENTREGAS_DISPONIVEIS,
            nivel_laboratorio=4,
            especies=especies_do_seed,
            grafo=grafo_de_kanto,
            visitados=visitados,
            cidades=[cidades_do_seed["pallet-town"], cidades_do_seed["viridian-city"]],
            gerador=GeradorSemeado(semente),
        )
        for pedido in pedidos:
            for requisito in pedido.requisitos:
                especie = por_id[requisito.especie_id]
                assert alcance.intersection(especie.locais_ids), especie.nome


MAPA_INTEIRO = {
    "pallet-town",
    "route-1",
    "viridian-city",
    "route-2",
    "route-22",
    "viridian-forest",
    "pewter-city",
    "route-3",
    "mt-moon",
    "cerulean-city",
}


def test_laboratorio_nivel_1_so_encomenda_especie_comum(
    especies_do_seed, grafo_de_kanto, cidades_do_seed
):
    # Criterio 14, com o MAPA INTEIRO aberto: mesmo alcancando Pikachu (190),
    # Clefairy (150) e Kakuna (120), o laboratorio nivel 1 nao pede nenhum
    # deles. Se o teste usasse so Pallet Town ele passaria sozinho, porque la
    # tudo e taxa 255.
    por_id = {especie.id: especie for especie in especies_do_seed}

    for semente in range(60):
        pedidos = gerar_pedidos(
            balance.ENTREGAS_DISPONIVEIS,
            nivel_laboratorio=1,
            especies=especies_do_seed,
            grafo=grafo_de_kanto,
            visitados=MAPA_INTEIRO,
            cidades=list(cidades_do_seed.values()),
            gerador=GeradorSemeado(semente),
        )
        for pedido in pedidos:
            for requisito in pedido.requisitos:
                especie = por_id[requisito.especie_id]
                assert especie.taxa_captura == balance.TAXA_CAPTURA_MAXIMA, especie.nome


def test_laboratorio_de_nivel_alto_encomenda_o_que_o_nivel_1_nao_encomendava(
    especies_do_seed, grafo_de_kanto, cidades_do_seed
):
    # Criterio 15: a banda do nivel alto inclui especies raras: Clefairy
    # (150), que vive em Mt. Moon e que o nivel 1 nunca pediria.
    por_id = {especie.id: especie for especie in especies_do_seed}
    pedidas: set[str] = set()

    for semente in range(60):
        pedidos = gerar_pedidos(
            balance.ENTREGAS_DISPONIVEIS,
            nivel_laboratorio=balance.NIVEL_LABORATORIO_BANDA_TOTAL,
            especies=especies_do_seed,
            grafo=grafo_de_kanto,
            visitados=MAPA_INTEIRO,
            cidades=list(cidades_do_seed.values()),
            gerador=GeradorSemeado(semente),
        )
        for pedido in pedidos:
            pedidas.update(por_id[requisito.especie_id].nome for requisito in pedido.requisitos)

    assert "Clefairy" in pedidas
    assert {"Kakuna", "Metapod"}.intersection(pedidas)


def test_pokedex_vazia_gera_normalmente(especies_do_seed, grafo_de_kanto, cidades_do_seed):
    # Criterio 13. Nao ha nada a passar: a Pokedex NAO entra na geracao, entao
    # um laboratorio recem-criado gera como qualquer outro.
    pedidos = gerar_pedidos(
        balance.ENTREGAS_DISPONIVEIS,
        nivel_laboratorio=1,
        especies=especies_do_seed,
        grafo=grafo_de_kanto,
        visitados={"pallet-town"},
        cidades=[cidades_do_seed["pallet-town"]],
        gerador=GeradorSemeado(7),
    )

    assert len(pedidos) == balance.ENTREGAS_DISPONIVEIS
    assert all(pedido.requisitos for pedido in pedidos)


# --- Forma do pedido ---------------------------------------------------------


def test_o_pedido_tem_no_maximo_tres_especies_e_todas_distintas(
    especies_do_seed, grafo_de_kanto, cidades_do_seed
):
    # Criterio 17.
    for semente in range(60):
        pedidos = gerar_pedidos(
            balance.ENTREGAS_DISPONIVEIS,
            nivel_laboratorio=6,
            especies=especies_do_seed,
            grafo=grafo_de_kanto,
            visitados={"pallet-town", "route-1", "viridian-city", "route-2", "viridian-forest"},
            cidades=[cidades_do_seed["pallet-town"], cidades_do_seed["viridian-city"]],
            gerador=GeradorSemeado(semente),
        )
        for pedido in pedidos:
            ids = [requisito.especie_id for requisito in pedido.requisitos]
            assert 1 <= len(ids) <= balance.ESPECIES_MAXIMAS_POR_ENTREGA
            assert len(set(ids)) == len(ids)


def test_a_quantidade_pedida_respeita_o_teto_da_especie(
    especies_do_seed, grafo_de_kanto, cidades_do_seed
):
    por_id = {especie.id: especie for especie in especies_do_seed}

    for semente in range(60):
        pedidos = gerar_pedidos(
            balance.ENTREGAS_DISPONIVEIS,
            nivel_laboratorio=6,
            especies=especies_do_seed,
            grafo=grafo_de_kanto,
            visitados={"pallet-town", "route-1", "viridian-city", "route-2", "viridian-forest"},
            cidades=[cidades_do_seed["viridian-city"]],
            gerador=GeradorSemeado(semente),
        )
        for pedido in pedidos:
            for requisito in pedido.requisitos:
                teto = teto_de_quantidade(por_id[requisito.especie_id].taxa_captura)
                assert 1 <= requisito.quantidade <= teto


def test_o_destino_e_uma_cidade_desbloqueada():
    pedido = gerar_pedido(
        candidatas=(PIDGEY,),
        cidades=(VIRIDIAN,),
        gerador=GeradorSemeado(1),
    )

    assert pedido.local_destino_id == "viridian-city"
    assert pedido.local_destino_nome == "Viridian City"
    assert pedido.titulo == "Encomenda para Viridian City"


def test_o_total_pedido_soma_as_quantidades():
    pedido = gerar_pedido(
        candidatas=(PIDGEY, RATTATA), cidades=(PALLET,), gerador=GeradorSemeado(3)
    )

    assert pedido.total_pedido == sum(requisito.quantidade for requisito in pedido.requisitos)


def test_sem_candidata_o_pedido_nao_e_gerado():
    with pytest.raises(SemEspecieCandidata):
        gerar_pedido(candidatas=(), cidades=(PALLET,), gerador=GeradorSemeado(1))


def test_sem_cidade_desbloqueada_o_pedido_nao_e_gerado():
    with pytest.raises(SemCidadeDeDestino):
        gerar_pedido(candidatas=(PIDGEY,), cidades=(), gerador=GeradorSemeado(1))


def test_quantidade_negativa_de_pedidos_e_recusada(especies_do_seed, grafo_de_kanto):
    with pytest.raises(ParametroDeEntregaInvalido):
        gerar_pedidos(
            -1,
            nivel_laboratorio=1,
            especies=especies_do_seed,
            grafo=grafo_de_kanto,
            visitados={"pallet-town"},
            cidades=(PALLET,),
            gerador=GeradorSemeado(1),
        )


# --- Teto de quantidade por raridade (questao 22 do SDD) --------------------

TABELA_DO_TETO = [
    (255, 3),  # Caterpie, o mais comum
    (190, 2),  # Pikachu
    (170, 2),
    (120, 1),  # Metapod
    (85, 1),
    (45, 1),  # Bulbasaur
    (3, 1),  # Mewtwo
    (0, 1),
]


@pytest.mark.parametrize(("taxa", "teto_esperado"), TABELA_DO_TETO)
def test_teto_de_quantidade_acompanha_a_taxa_de_captura(taxa, teto_esperado):
    assert teto_de_quantidade(taxa) == teto_esperado


# --- Determinismo (Artigo III) ----------------------------------------------


def test_a_mesma_semente_gera_o_mesmo_pedido(especies_do_seed, grafo_de_kanto, cidades_do_seed):
    def sortear():
        return gerar_pedidos(
            balance.ENTREGAS_DISPONIVEIS,
            nivel_laboratorio=5,
            especies=especies_do_seed,
            grafo=grafo_de_kanto,
            visitados={"pallet-town", "route-1", "viridian-city"},
            cidades=[cidades_do_seed["pallet-town"], cidades_do_seed["viridian-city"]],
            gerador=GeradorSemeado(20261107),
        )

    assert sortear() == sortear()


def test_sementes_diferentes_nao_produzem_sempre_a_mesma_lista(
    especies_do_seed, grafo_de_kanto, cidades_do_seed
):
    listas = {
        gerar_pedidos(
            balance.ENTREGAS_DISPONIVEIS,
            nivel_laboratorio=5,
            especies=especies_do_seed,
            grafo=grafo_de_kanto,
            visitados={"pallet-town", "route-1", "viridian-city"},
            cidades=[cidades_do_seed["pallet-town"], cidades_do_seed["viridian-city"]],
            gerador=GeradorSemeado(semente),
        )
        for semente in range(20)
    }

    assert len(listas) > 1


def test_a_ordem_das_rolagens_e_contrato():
    # 1. destino, 2. quantas especies, 3. por especie: indice e quantidade.
    gerador = GeradorRoteirizado(inteiros=[1, 2, 0, 3, 0, 2])

    pedido = gerar_pedido(
        candidatas=(PIDGEY, RATTATA, PIKACHU),
        cidades=(PALLET, VIRIDIAN),
        gerador=gerador,
    )

    assert gerador.chamadas == [
        "randint(0,1)",  # destino entre as duas cidades, ordenadas por id
        "randint(1,3)",  # quantas especies
        "randint(0,2)",  # primeira especie, entre as tres candidatas
        "randint(1,3)",  # quantidade, limitada pelo teto de Pidgey (255 -> 3)
        "randint(0,1)",  # segunda especie, entre as duas que sobraram
        "randint(1,3)",  # quantidade, teto de Rattata (255 -> 3)
    ]
    assert pedido.local_destino_id == "viridian-city"
    assert pedido.requisitos == (
        RequisitoDoPedido(especie_id=16, especie_nome="Pidgey", quantidade=3),
        RequisitoDoPedido(especie_id=19, especie_nome="Rattata", quantidade=2),
    )


def test_a_ordem_dos_requisitos_nao_depende_da_ordem_do_sorteio():
    # O roteiro tira Rattata primeiro; o pedido sai ordenado por especie_id.
    gerador = GeradorRoteirizado(inteiros=[0, 2, 1, 1, 0, 1])

    pedido = gerar_pedido(
        candidatas=(PIDGEY, RATTATA, PIKACHU),
        cidades=(PALLET,),
        gerador=gerador,
    )

    assert [requisito.especie_id for requisito in pedido.requisitos] == [16, 19]


# --- Prazo da oferta: EXPIRADA e derivada, nunca gravada --------------------


def test_a_oferta_nasce_com_o_prazo_de_balance():
    assert duracao_da_oferta() == timedelta(minutes=balance.VALIDADE_ENTREGA_MINUTOS)


def test_o_prazo_da_oferta_sobrevive_a_expedicao_mais_longa_do_mapa():
    # Mt. Moon partindo de Pallet Town leva 55 minutos (SDD 4.4). Um prazo mais
    # curto que isso faria do pedido uma oferta que nunca foi oferta.
    duracao_de_mt_moon = timedelta(minutes=55)

    assert duracao_da_oferta() > duracao_de_mt_moon


def test_a_escala_multiplica_o_prazo_da_oferta():
    assert duracao_da_oferta(ESCALA_DE_DESENVOLVIMENTO) == timedelta(
        minutes=balance.VALIDADE_ENTREGA_MINUTOS * ESCALA_DE_DESENVOLVIMENTO
    )


def test_o_prazo_tem_piso_de_um_segundo():
    assert duracao_da_oferta(0.0000001) == timedelta(seconds=1)


def test_escala_invalida_no_prazo_e_recusada():
    with pytest.raises(ParametroDeEntregaInvalido):
        duracao_da_oferta(0.0)


def test_expiracao_da_oferta_soma_o_prazo_ao_instante_de_geracao():
    prazo = timedelta(minutes=balance.VALIDADE_ENTREGA_MINUTOS)

    assert expiracao_da_oferta(AGORA) == AGORA + prazo


def test_a_geracao_sem_fuso_e_recusada():
    with pytest.raises(RelogioSemFuso):
        expiracao_da_oferta(datetime(2026, 11, 7, 12, 0))


TABELA_DE_ESTADOS = [
    # (status gravado, expira_em, eta, estado observado)
    ("DISPONIVEL", AGORA + timedelta(minutes=1), None, EstadoObservadoEntrega.DISPONIVEL),
    ("DISPONIVEL", AGORA + timedelta(microseconds=1), None, EstadoObservadoEntrega.DISPONIVEL),
    # No empate, a oferta JA venceu: expira_em e o instante em que ela sai de
    # circulacao, nao o ultimo instante em que vale.
    ("DISPONIVEL", AGORA, None, EstadoObservadoEntrega.EXPIRADA),
    ("DISPONIVEL", AGORA - timedelta(microseconds=1), None, EstadoObservadoEntrega.EXPIRADA),
    ("DISPONIVEL", AGORA - timedelta(hours=3), None, EstadoObservadoEntrega.EXPIRADA),
    # O prazo e DA OFERTA, nao da missao: aceita, a entrega nao expira mais.
    (
        "EM_CURSO",
        AGORA - timedelta(hours=3),
        AGORA + timedelta(minutes=5),
        EstadoObservadoEntrega.EM_CURSO,
    ),
    ("EM_CURSO", None, AGORA - timedelta(minutes=5), EstadoObservadoEntrega.EM_CURSO),
    ("CONCLUIDA", AGORA - timedelta(hours=9), AGORA, EstadoObservadoEntrega.CONCLUIDA),
    ("DESCARTADA", AGORA - timedelta(hours=9), None, EstadoObservadoEntrega.DESCARTADA),
]


@pytest.mark.parametrize(("status", "expira_em", "eta", "esperado"), TABELA_DE_ESTADOS)
def test_estado_observado_da_entrega(status, expira_em, eta, esperado):
    assert estado_observado_entrega(status, expira_em, eta, AGORA) is esperado


def test_a_expiracao_nao_muda_o_status_gravado():
    # Criterio 19 da spec 008 no que o dominio alcanca: a derivacao e leitura
    # pura. A coluna continua DISPONIVEL depois de a funcao dizer EXPIRADA.
    status_gravado = StatusEntrega.DISPONIVEL
    vencido = AGORA - timedelta(minutes=1)

    observado = estado_observado_entrega(status_gravado, vencido, None, AGORA)

    assert observado is EstadoObservadoEntrega.EXPIRADA
    assert status_gravado is StatusEntrega.DISPONIVEL
    assert estado_observado_entrega(status_gravado, vencido, None, AGORA) is observado


def test_a_oferta_expirada_deixa_de_ser_aceitavel():
    # Criterios 18 e 20.
    vencida = estado_observado_entrega("DISPONIVEL", AGORA, None, AGORA)
    valida = estado_observado_entrega("DISPONIVEL", AGORA + timedelta(minutes=1), None, AGORA)

    assert not vencida.aceitavel
    assert valida.aceitavel


def test_oferta_disponivel_sem_prazo_e_dado_corrompido():
    with pytest.raises(PrazoDeEntregaAusente):
        estado_observado_entrega("DISPONIVEL", None, None, AGORA)


def test_entrega_em_curso_sem_eta_e_dado_corrompido():
    with pytest.raises(PrazoDeEntregaAusente):
        estado_observado_entrega("EM_CURSO", AGORA, None, AGORA)


def test_status_desconhecido_e_recusado():
    from app.game.delivery import StatusDeEntregaDesconhecido

    with pytest.raises(StatusDeEntregaDesconhecido):
        estado_observado_entrega("ENTREGUE", AGORA, None, AGORA)


@pytest.mark.parametrize(
    ("expira_em", "agora"),
    [
        (datetime(2026, 11, 7, 12, 0), AGORA),
        (AGORA, datetime(2026, 11, 7, 12, 0)),
    ],
)
def test_datetime_sem_fuso_e_recusado_em_vez_de_estourar(expira_em, agora):
    with pytest.raises(RelogioSemFuso):
        estado_observado_entrega("DISPONIVEL", expira_em, None, agora)


TABELA_DE_SEGUNDOS_PARA_EXPIRAR = [
    (timedelta(minutes=2), 120),
    (timedelta(seconds=1), 1),
    (timedelta(microseconds=1), 1),  # sobrando qualquer fracao, falta um segundo
    (timedelta(0), 0),
    (timedelta(minutes=-5), 0),
]


@pytest.mark.parametrize(("falta", "segundos"), TABELA_DE_SEGUNDOS_PARA_EXPIRAR)
def test_segundos_para_expirar(falta, segundos):
    assert segundos_para_expirar(AGORA + falta, AGORA) == segundos


def test_zero_segundos_para_expirar_acontece_exatamente_quando_expira():
    # A contagem regressiva e o estado observado nao se contradizem no limite.
    for microssegundos in (-1, 0, 1):
        expira_em = AGORA + timedelta(microseconds=microssegundos)
        estado = estado_observado_entrega("DISPONIVEL", expira_em, None, AGORA)
        segundos = segundos_para_expirar(expira_em, AGORA)

        assert (segundos == 0) == (estado is EstadoObservadoEntrega.EXPIRADA)


# --- Regeracao da lista (invariantes 15 e 23) -------------------------------


def test_regerar_a_lista_valida_espera_o_intervalo():
    # Criterio 22: a recusa precisa dizer quanto falta.
    ultimo = AGORA - timedelta(minutes=5)

    assert segundos_para_regerar(ultimo, AGORA) == timedelta(minutes=10).seconds


def test_passado_o_intervalo_nao_ha_mais_espera():
    ultimo = AGORA - timedelta(minutes=balance.INTERVALO_REGERAR_ENTREGAS_MINUTOS)

    assert segundos_para_regerar(ultimo, AGORA) == 0


def test_sem_sorteio_anterior_nao_ha_espera():
    assert segundos_para_regerar(None, AGORA) == 0


def test_a_escala_multiplica_o_intervalo_de_regeracao():
    ultimo = AGORA - timedelta(seconds=5)

    assert proxima_regeracao(ultimo, ESCALA_DE_DESENVOLVIMENTO) == ultimo + timedelta(
        minutes=balance.INTERVALO_REGERAR_ENTREGAS_MINUTOS * ESCALA_DE_DESENVOLVIMENTO
    )
    assert segundos_para_regerar(ultimo, AGORA, ESCALA_DE_DESENVOLVIMENTO) == 4


TABELA_DE_VAGAS = [
    ((), balance.ENTREGAS_DISPONIVEIS),
    ((EstadoObservadoEntrega.DISPONIVEL,) * 3, 0),
    ((EstadoObservadoEntrega.DISPONIVEL,) * 2 + (EstadoObservadoEntrega.EXPIRADA,), 1),
    (
        (
            EstadoObservadoEntrega.EXPIRADA,
            EstadoObservadoEntrega.EM_CURSO,
            EstadoObservadoEntrega.CONCLUIDA,
            EstadoObservadoEntrega.DESCARTADA,
        ),
        balance.ENTREGAS_DISPONIVEIS,
    ),
    ((EstadoObservadoEntrega.DISPONIVEL,) * 5, 0),
]


@pytest.mark.parametrize(("estados", "vagas"), TABELA_DE_VAGAS)
def test_vagas_para_repor(estados, vagas):
    # Criterio 21: a vaga aberta por expiracao ou por aceite e reposta, e o
    # intervalo de regeracao nao entra nessa conta.
    assert vagas_para_repor(estados) == vagas


# --- Duracao da entrega (SDD 4.9) -------------------------------------------

TABELA_DE_DURACAO = [
    # (custo de viagem, nivel do treinador, escala, minutos)
    (10, None, 1.0, 20),  # so ida e volta
    (0, None, 1.0, 1),  # piso: uma entrega de zero minuto chegaria ao partir
    (10, 5, 1.0, 18),  # -10% por nivel 5
    (10, 20, 1.0, 12),  # -40%, o teto do desconto
    (10, 99, 1.0, 12),  # o desconto nao passa do teto
    (5, 3, 1.0, 9),  # 5 * 2 * 0.94 = 9.4, arredondado UMA vez no fim
    (30, None, 2.0, 120),  # a escala MULTIPLICA
    (30, None, ESCALA_DE_DESENVOLVIMENTO, 1),
]


@pytest.mark.parametrize(("custo", "nivel", "escala", "minutos"), TABELA_DE_DURACAO)
def test_duracao_da_entrega(custo, nivel, escala, minutos):
    assert (
        duracao_da_entrega(custo_viagem_minutos=custo, nivel_treinador=nivel, escala=escala)
        == minutos
    )


def test_a_escala_multiplica_a_duracao_da_entrega():
    normal = duracao_da_entrega(custo_viagem_minutos=34)
    dobrada = duracao_da_entrega(custo_viagem_minutos=34, escala=2.0)
    encolhida = duracao_da_entrega(custo_viagem_minutos=34, escala=ESCALA_DE_DESENVOLVIMENTO)

    assert dobrada == normal * 2
    assert encolhida < normal


def test_a_entrega_e_ida_e_volta_e_a_expedicao_nao():
    # Mesma viagem: a entrega dobra a estrada e nao explora nada.
    so_ida = mapa.duracao_estimada(custo_viagem_minutos=12, encontros_base=0)

    assert duracao_da_entrega(custo_viagem_minutos=12) == so_ida * 2


def test_custo_de_viagem_negativo_e_recusado():
    with pytest.raises(ParametroDeEntregaInvalido):
        duracao_da_entrega(custo_viagem_minutos=-1)


def test_escala_invalida_na_duracao_e_recusada():
    with pytest.raises(ParametroDeEntregaInvalido):
        duracao_da_entrega(custo_viagem_minutos=10, escala=-1.0)


# --- Recompensa (SDD 4.9, criterio 27) --------------------------------------

TABELA_DE_MOEDAS = [
    # (nivel, viagem, moedas do unico Pokemon entregue)
    (1, 0, 30),  # 25 + 1*5
    (10, 0, 75),
    (10, 30, 150),  # viagem de 30 minutos dobra
    (10, 60, 225),  # e de 60, triplica
    (5, 15, 75),  # (25 + 25) * 1,5
    (100, 0, 525),
]


@pytest.mark.parametrize(("nivel", "viagem", "moedas"), TABELA_DE_MOEDAS)
def test_moedas_por_pokemon_entregue(nivel, viagem, moedas):
    recompensa = recompensa_da_entrega(
        [PokemonEntregue(especie_nome="Pidgey", nivel=nivel)],
        custo_viagem_minutos=viagem,
    )

    assert recompensa.moedas == moedas


def test_entregar_longe_paga_mais():
    perto = recompensa_da_entrega(
        [PokemonEntregue(especie_nome="Pidgey", nivel=8)], custo_viagem_minutos=3
    )
    longe = recompensa_da_entrega(
        [PokemonEntregue(especie_nome="Pidgey", nivel=8)], custo_viagem_minutos=34
    )

    assert longe.moedas > perto.moedas


def test_entregar_nivel_alto_paga_mais():
    baixo = recompensa_da_entrega(
        [PokemonEntregue(especie_nome="Pidgey", nivel=5)], custo_viagem_minutos=10
    )
    alto = recompensa_da_entrega(
        [PokemonEntregue(especie_nome="Pidgey", nivel=40)], custo_viagem_minutos=10
    )

    assert alto.moedas > baixo.moedas


def test_a_moeda_e_a_soma_das_parcelas_arredondada_uma_vez():
    # Cada parcela sai em Fraction de proposito: arredondar parcela a parcela
    # faria o total depender de como os Pokemon foram agrupados.
    entregues = [
        PokemonEntregue(especie_nome="Pidgey", nivel=4),
        PokemonEntregue(especie_nome="Rattata", nivel=7),
    ]

    recompensa = recompensa_da_entrega(entregues, custo_viagem_minutos=11)
    soma_exata = sum(moedas_por_pokemon(entregue.nivel, 11) for entregue in entregues)

    assert recompensa.moedas == round(soma_exata)


def test_a_experiencia_do_laboratorio_cresce_com_o_tamanho_da_encomenda():
    recompensa = recompensa_da_entrega(
        [
            PokemonEntregue(especie_nome="Pidgey", nivel=4),
            PokemonEntregue(especie_nome="Pidgey", nivel=6),
            PokemonEntregue(especie_nome="Rattata", nivel=9),
        ],
        custo_viagem_minutos=6,
    )

    assert recompensa.total_entregue == 3
    assert recompensa.exp_laboratorio == balance.EXP_LAB_POR_ENTREGA * 3
    assert recompensa.exp_treinador == balance.EXP_TREINADOR_POR_ENTREGA


def test_a_experiencia_do_treinador_e_por_entrega_e_nao_por_pokemon():
    uma = recompensa_da_entrega(
        [PokemonEntregue(especie_nome="Pidgey", nivel=4)], custo_viagem_minutos=6
    )
    tres = recompensa_da_entrega(
        [PokemonEntregue(especie_nome="Pidgey", nivel=4)] * 3, custo_viagem_minutos=6
    )

    assert uma.exp_treinador == tres.exp_treinador


def test_entrega_sem_pokemon_e_chamada_errada():
    with pytest.raises(ParametroDeEntregaInvalido):
        recompensa_da_entrega([], custo_viagem_minutos=6)


def test_pokemon_acima_do_nivel_maximo_e_recusado():
    from app.game.erros import NivelInvalido

    with pytest.raises(NivelInvalido):
        recompensa_da_entrega(
            [PokemonEntregue(especie_nome="Pidgey", nivel=balance.NIVEL_MAXIMO + 1)],
            custo_viagem_minutos=6,
        )


# --- Conferencia do aceite (criterios 23 e 24) ------------------------------

PEDIDO_DE_DOIS_PIDGEY = (RequisitoDoPedido(especie_id=16, especie_nome="Pidgey", quantidade=2),)


def test_dois_pidgey_escolhidos_atendem_ao_pedido_de_dois_pidgey():
    exigir_pokemon_que_atendem(PEDIDO_DE_DOIS_PIDGEY, [16, 16])


def test_um_pidgey_e_um_rattata_nao_atendem_ao_pedido_de_dois_pidgey():
    with pytest.raises(PokemonNaoAtendeAoPedido) as excecao:
        exigir_pokemon_que_atendem(PEDIDO_DE_DOIS_PIDGEY, [16, 19])

    assert excecao.value.detalhes == {"faltando": {16: 1}, "sobrando": {19: 1}}


@pytest.mark.parametrize("escolhidos", [[16], [16, 16, 16], []])
def test_quantidade_diferente_da_pedida_e_recusada(escolhidos):
    with pytest.raises(PokemonNaoAtendeAoPedido):
        exigir_pokemon_que_atendem(PEDIDO_DE_DOIS_PIDGEY, escolhidos)


def test_a_ordem_dos_escolhidos_nao_importa():
    pedido = (
        RequisitoDoPedido(especie_id=16, especie_nome="Pidgey", quantidade=2),
        RequisitoDoPedido(especie_id=19, especie_nome="Rattata", quantidade=1),
    )

    exigir_pokemon_que_atendem(pedido, [19, 16, 16])
