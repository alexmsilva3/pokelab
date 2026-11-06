"""Despacho de expedicao: dificuldade, chance, prazo e estado observado (spec 006).

O grafo de Kanto abaixo e transcrito de `data/seed/locations.json` a mao, pelo
mesmo motivo de `test_game_mapa.py`: um teste de dominio que le o seed passa a
testar duas coisas ao mesmo tempo e deixa de dizer qual das duas quebrou.

As dificuldades e as chances da tabela foram calculadas a mao a partir da
secao 4.3 do SDD — `media(faixa) * nivel_dificuldade * FATOR_DIFICULDADE` e a
sigmoide de inclinacao 2,5 achatada entre 5% e 95%.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from app.game import balance
from app.game.erros import ErroDeDominio
from app.game.expedition import (
    CargaInvalida,
    DespachoCalculado,
    EstadoObservado,
    EstoqueInsuficiente,
    ItemNaCarga,
    LocalDaExpedicao,
    LocalInvalido,
    PoderInvalido,
    RelogioSemFuso,
    SementeInvalida,
    StatusExpedicao,
    TimeVazio,
    TreinadorIndisponivel,
    TreinadorParaExpedicao,
    bonus_de_itens,
    calcular_despacho,
    chance_estimada,
    dificuldade_do_local,
    estado_observado,
    prever_despacho,
    tempo_restante,
)
from app.game.mapa import DestinoForaDeAlcance, LocalDesconhecido, LocalNoGrafo, montar_grafo
from app.game.power import PokemonNoTime
from app.game.team import TimeCheio
from app.game.trainers import StatusTreinador

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

PALLET = LocalDaExpedicao("pallet-town", 2, 4, 1)
ROUTE_1 = LocalDaExpedicao("route-1", 2, 5, 1)
VIRIDIAN = LocalDaExpedicao("viridian-city", 3, 6, 2)
MT_MOON = LocalDaExpedicao("mt-moon", 7, 12, 5)

# --- Treinador, time e carga ------------------------------------------------

TREINADOR_ID = UUID("00000000-0000-4000-8000-000000000001")
AGORA = datetime(2026, 11, 6, 12, 0, tzinfo=UTC)
SEED = 1234567

# Bulbasaur nivel 5: 45+49+49+65+65+45 = 318 de stats base.
BULBASAUR = PokemonNoTime(nivel=5, soma_stats_base=318, hp_atual_pct=100)
CHARMANDER = PokemonNoTime(nivel=5, soma_stats_base=309, hp_atual_pct=100)

POCAO = ItemNaCarga("potion", 1, 5, efeito_duracao=0.02)
POKEBOLA = ItemNaCarga("poke-ball", 3, 10, efeito_duracao=0.0)


def treinador(
    *, nivel: int = 1, status: StatusTreinador = StatusTreinador.DISPONIVEL
) -> TreinadorParaExpedicao:
    return TreinadorParaExpedicao(id=TREINADOR_ID, nivel=nivel, status=status)


def despachar(**trocas) -> DespachoCalculado:
    """O despacho padrao da suite: Pallet Town, Route 1, um Bulbasaur."""
    argumentos = {
        "treinador": treinador(),
        "time": [BULBASAUR],
        "grafo": KANTO,
        "visitados": SO_PALLET,
        "destino": ROUTE_1,
        "seed": SEED,
        "agora": AGORA,
    }
    argumentos.update(trocas)
    return calcular_despacho(**argumentos)


# --- Dificuldade (SDD 4.3) --------------------------------------------------


@pytest.mark.parametrize(
    ("local", "esperada"),
    [
        # media da faixa * nivel_dificuldade * FATOR_DIFICULDADE (1,0)
        (LocalDaExpedicao("pallet-town", 2, 4, 1), 3.0),  # 3 * 1
        (LocalDaExpedicao("route-1", 2, 5, 1), 3.5),  # 3,5 * 1
        (LocalDaExpedicao("viridian-city", 3, 6, 2), 9.0),  # 4,5 * 2
        (LocalDaExpedicao("viridian-forest", 4, 8, 3), 18.0),  # 6 * 3
        (LocalDaExpedicao("route-22", 6, 10, 5), 40.0),  # 8 * 5
        (LocalDaExpedicao("mt-moon", 7, 12, 5), 47.5),  # 9,5 * 5
        (LocalDaExpedicao("cerulean-city", 10, 14, 6), 72.0),  # 12 * 6
    ],
)
def test_tabela_de_dificuldade_do_local(local: LocalDaExpedicao, esperada: float) -> None:
    assert dificuldade_do_local(local) == esperada


def test_faixa_de_nivel_selvagem_com_meio_ponto_nao_e_arredondada_antes():
    """Mt. Moon tem media 9,5, e nao 9 nem 10: meio ponto vale 2,5 de dificuldade."""
    assert dificuldade_do_local(MT_MOON) == 47.5
    assert dificuldade_do_local(LocalDaExpedicao("quase", 7, 11, 5)) == 45.0


def test_local_degenerado_tem_dificuldade_zero():
    assert dificuldade_do_local(LocalDaExpedicao("vazio", 1, 1, 0)) == 0.0


@pytest.mark.parametrize(
    "argumentos",
    [
        (0, 4, 1),  # nivel selvagem abaixo de 1
        (4, 2, 1),  # faixa invertida
        (2, balance.NIVEL_MAXIMO + 1, 1),  # acima do nivel maximo
        (2, 4, -1),  # dificuldade negativa
    ],
)
def test_local_com_numeros_impossiveis_e_recusado(argumentos: tuple[int, int, int]) -> None:
    with pytest.raises(LocalInvalido):
        LocalDaExpedicao("quebrado", *argumentos)


# --- Chance estimada (SDD 4.3) ----------------------------------------------


@pytest.mark.parametrize(
    ("poder", "dificuldade", "esperada"),
    [
        (3.0, 3.0, 0.5),  # razao 1: a sigmoide passa exatamente no meio
        (6.0, 3.0, 0.9241),  # razao 2
        (1.5, 3.0, 0.2227),  # razao 0,5
        (0.6, 3.0, 0.1192),  # razao 0,2
        (0.0, 3.0, 0.0759),  # time sem poder nenhum ainda tem 7,6%
        (47.5, 47.5, 0.5),  # Mt. Moon em pe de igualdade
        (100.0, 47.5, 0.9407),  # razao 2,105
        (10.0, 47.5, 0.122),  # razao 0,21
        (9.0, 3.0, balance.P_VITORIA_MAXIMA),  # razao 3 ja estoura o teto
    ],
)
def test_tabela_de_chance_estimada(poder: float, dificuldade: float, esperada: float) -> None:
    assert chance_estimada(poder, dificuldade) == esperada


@pytest.mark.parametrize(
    "razao",
    [0.0, 1e-9, 0.001, 0.5, 0.999, 1.0, 1.001, 2.0, 10.0, 1e6, 1e12, 1e300],
)
def test_a_chance_nunca_passa_dos_limites(razao: float) -> None:
    """Expedicao suicida ainda pode dar certo; trivial ainda pode falhar."""
    chance = chance_estimada(razao, 1.0)
    assert balance.P_VITORIA_MINIMA <= chance <= balance.P_VITORIA_MAXIMA


def test_razao_absurda_para_cima_satura_no_teto():
    assert chance_estimada(1e308, 1e-10) == balance.P_VITORIA_MAXIMA


def test_com_a_inclinacao_de_hoje_o_piso_nunca_aperta():
    """A razao nunca e negativa, entao a sigmoide nao desce abaixo de 1/(1+e^2,5).

    Com `INCLINACAO_SIGMOIDE` em 2,5 o pior caso possivel e 7,6%, acima do piso
    de 5%: o clamp inferior e garantia para a calibragem da Fase 9, nao um
    limite que a formula de hoje encosta. Registrar isso evita que alguem
    conclua, de um teste verde, que o piso esta sendo exercitado.
    """
    pior_caso = chance_estimada(0.0, 1e308)
    assert pior_caso == 0.0759
    assert pior_caso > balance.P_VITORIA_MINIMA


def test_razao_absurda_para_baixo_satura_no_piso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com inclinacao calibrada para 5, o piso passa a apertar — e segura."""
    monkeypatch.setattr(balance, "INCLINACAO_SIGMOIDE", 5.0)
    assert chance_estimada(1e-10, 1e308) == balance.P_VITORIA_MINIMA


def test_dificuldade_zero_nao_divide_por_zero():
    """Lugar sem perigo nenhum e vencido por qualquer time, inclusive pelo vazio."""
    assert chance_estimada(0.0, 0.0) == balance.P_VITORIA_MAXIMA
    assert chance_estimada(1234.5, 0.0) == balance.P_VITORIA_MAXIMA


def test_a_chance_cresce_com_o_poder():
    anterior = 0.0
    for poder in range(0, 200, 7):
        atual = chance_estimada(float(poder), 47.5)
        assert atual >= anterior
        anterior = atual


@pytest.mark.parametrize(("poder", "dificuldade"), [(-1.0, 3.0), (3.0, -1.0)])
def test_poder_ou_dificuldade_negativos_sao_chamada_errada(
    poder: float, dificuldade: float
) -> None:
    with pytest.raises(PoderInvalido):
        chance_estimada(poder, dificuldade)


# --- Bonus de itens (SDD 4.4) -----------------------------------------------


def test_bonus_de_itens_soma_por_quantidade():
    carga = [ItemNaCarga("potion", 5, 10, efeito_duracao=0.02)]
    assert bonus_de_itens(carga) == pytest.approx(0.10)


def test_bonus_de_itens_respeita_o_teto():
    carga = [ItemNaCarga("revive", 20, 20, efeito_duracao=0.05)]
    assert bonus_de_itens(carga) == balance.BONUS_ITENS_MAXIMO


def test_pokebola_nao_acelera_nada():
    assert bonus_de_itens([POKEBOLA]) == 0.0
    assert bonus_de_itens([]) == 0.0


def test_item_que_atrasaria_a_expedicao_e_chamada_errada():
    """Nenhum item do seed tem efeito negativo; se chegar um, e dado corrompido."""
    with pytest.raises(CargaInvalida):
        bonus_de_itens([ItemNaCarga("pedra", 1, 1, efeito_duracao=-0.5)])


# --- Despacho: o caminho feliz ----------------------------------------------


def test_despacho_devolve_rota_prazo_semente_poder_e_dificuldade():
    despacho = despachar()

    assert despacho.treinador_id == TREINADOR_ID
    assert despacho.destino_id == "route-1"
    assert despacho.origem_id == "pallet-town"
    assert despacho.caminho == ("pallet-town", "route-1")
    assert despacho.custo_viagem_minutos == ROTA
    # (4 de viagem + 3 encontros * 3 minutos) * 0,98 = 12,74 -> 13 minutos
    assert despacho.duracao_minutos == 13
    assert despacho.started_at == AGORA
    assert despacho.eta == AGORA + timedelta(minutes=13)
    assert despacho.seed == SEED
    # Bulbasaur nivel 5 com 318 de stats: 5 * 1,53 = 7,65, com treinador 1: 7,88
    assert despacho.poder_time == 7.9
    assert despacho.dificuldade == 3.5
    assert despacho.chance_estimada == chance_estimada(7.9, 3.5)
    assert despacho.capacidade_bagagem == balance.CAPACIDADE_TOTAL_TREINADOR - 1
    assert despacho.bonus_itens == 0.0
    assert despacho.carga == ()


def test_o_eta_sai_da_duracao_gravada():
    despacho = despachar(destino=MT_MOON, visitados=("pallet-town", "route-3"))
    assert despacho.eta - despacho.started_at == timedelta(minutes=despacho.duracao_minutos)


def test_carga_de_suporte_encurta_a_expedicao():
    sem_itens = despachar()
    com_itens = despachar(carga=[ItemNaCarga("potion", 5, 5, efeito_duracao=0.02)])
    # 12,74 * 0,90 = 11,466 -> 11 minutos
    assert com_itens.duracao_minutos == 11
    assert com_itens.duracao_minutos < sem_itens.duracao_minutos
    assert com_itens.bonus_itens == pytest.approx(0.10)


def test_treinador_experiente_e_mais_rapido_e_mais_forte():
    novato = despachar(treinador=treinador(nivel=1))
    veterano = despachar(treinador=treinador(nivel=20))
    assert veterano.duracao_minutos < novato.duracao_minutos
    assert veterano.poder_time > novato.poder_time


def test_a_carga_sai_ordenada_para_o_debito():
    despacho = despachar(carga=[POKEBOLA, POCAO])
    assert despacho.debitos == (("poke-ball", 3), ("potion", 1))


# --- Despacho: a escala de tempo do ADR-004 ---------------------------------


def test_a_escala_multiplica_e_portanto_encurta():
    """O SDD dizia 'divide' ate a Fase 5 e isso era um bug do documento."""
    normal = despachar(destino=MT_MOON, visitados=("pallet-town", "route-3"), escala=1.0)
    acelerada = despachar(destino=MT_MOON, visitados=("pallet-town", "route-3"), escala=0.01)

    assert acelerada.duracao_minutos < normal.duracao_minutos
    assert acelerada.duracao_minutos == balance.DURACAO_MINIMA_MINUTOS
    assert acelerada.eta < normal.eta


def test_escala_acima_de_um_alonga():
    normal = despachar()
    lenta = despachar(escala=10.0)
    assert lenta.duracao_minutos > normal.duracao_minutos


def test_nenhuma_expedicao_termina_no_instante_em_que_parte():
    acelerada = despachar(escala=0.000001)
    assert acelerada.eta > acelerada.started_at


# --- Despacho: os invariantes do SDD 3.3 ------------------------------------


def test_invariante_17_time_vazio_e_recusado():
    with pytest.raises(TimeVazio) as recusa:
        despachar(time=[])
    assert recusa.value.codigo == "TIME_VAZIO"
    assert recusa.value.detalhes["treinador_id"] == str(TREINADOR_ID)


@pytest.mark.parametrize("status", [StatusTreinador.EM_EXPEDICAO, StatusTreinador.EM_ENTREGA])
def test_invariante_3_treinador_ocupado_e_recusado(status: StatusTreinador) -> None:
    with pytest.raises(TreinadorIndisponivel) as recusa:
        despachar(treinador=treinador(status=status))
    assert recusa.value.codigo == "TREINADOR_OCUPADO"
    assert recusa.value.detalhes["status"] == status.value


def test_treinador_descansando_ainda_pode_ser_despachado():
    """DESCANSANDO nao e ocupado: o descanso adia a missao, nao a impede."""
    despacho = despachar(treinador=treinador(status=StatusTreinador.DESCANSANDO))
    assert despacho.destino_id == "route-1"


def test_invariante_6_destino_fora_de_alcance_e_recusado():
    with pytest.raises(DestinoForaDeAlcance) as recusa:
        despachar(destino=MT_MOON)
    assert recusa.value.codigo == "DESTINO_FORA_DE_ALCANCE"
    assert recusa.value.detalhes["proximo_passo_id"] == "route-1"


def test_destino_ja_visitado_e_alcancavel():
    despacho = despachar(destino=PALLET)
    assert despacho.custo_viagem_minutos == 0
    assert despacho.destino_id == "pallet-town"


def test_invariante_9_carga_maior_que_o_estoque_e_recusada():
    with pytest.raises(EstoqueInsuficiente) as recusa:
        despachar(carga=[ItemNaCarga("potion", 6, 5, efeito_duracao=0.02)])
    assert recusa.value.codigo == "ESTOQUE_INSUFICIENTE"
    assert recusa.value.detalhes == {"item_id": "potion", "pedido": 6, "disponivel": 5}


def test_carga_igual_ao_estoque_passa():
    despacho = despachar(carga=[ItemNaCarga("potion", 5, 5, efeito_duracao=0.02)])
    assert despacho.debitos == (("potion", 5),)


def test_item_repetido_na_carga_e_recusado():
    """Duas linhas de duas Pocoes contra um estoque de tres passariam uma a uma."""
    with pytest.raises(CargaInvalida) as recusa:
        despachar(
            carga=[
                ItemNaCarga("potion", 2, 3, efeito_duracao=0.02),
                ItemNaCarga("potion", 2, 3, efeito_duracao=0.02),
            ]
        )
    assert recusa.value.codigo == "CARGA_INVALIDA"


@pytest.mark.parametrize("quantidade", [0, -1])
def test_quantidade_nao_positiva_na_carga_e_recusada(quantidade: int) -> None:
    with pytest.raises(CargaInvalida):
        despachar(carga=[ItemNaCarga("potion", quantidade, 5)])


def test_estoque_negativo_e_dado_corrompido():
    with pytest.raises(CargaInvalida):
        despachar(carga=[ItemNaCarga("potion", 1, -1)])


def test_invariante_1_time_maior_que_o_maximo_e_recusado():
    time = [BULBASAUR] * (balance.TAMANHO_MAXIMO_TIME + 1)
    with pytest.raises(TimeCheio):
        despachar(time=time)


def test_semente_fora_da_faixa_e_recusada():
    with pytest.raises(SementeInvalida):
        despachar(seed=-1)
    with pytest.raises(SementeInvalida):
        despachar(seed=balance.SEED_MAXIMO + 1)


def test_destino_inexistente_no_mapa_nao_e_recusa_e_sim_404():
    with pytest.raises(LocalDesconhecido):
        despachar(destino=LocalDaExpedicao("saffron-city", 10, 14, 6))


def test_relogio_sem_fuso_e_recusado_na_entrada():
    with pytest.raises(RelogioSemFuso):
        despachar(agora=datetime(2026, 11, 6, 12, 0))


def test_treinador_ocupado_vence_as_demais_recusas():
    """Com o treinador em expedicao nenhuma outra escolha importa."""
    with pytest.raises(TreinadorIndisponivel):
        despachar(
            treinador=treinador(status=StatusTreinador.EM_EXPEDICAO),
            time=[],
            destino=MT_MOON,
            carga=[ItemNaCarga("potion", 99, 1)],
        )


# --- Previa -----------------------------------------------------------------


def test_previa_e_despacho_concordam_quando_a_escolha_e_valida():
    previa = prever_despacho(
        treinador=treinador(),
        time=[BULBASAUR, CHARMANDER],
        grafo=KANTO,
        visitados=SO_PALLET,
        destino=ROUTE_1,
        seed=SEED,
        agora=AGORA,
        carga=[POCAO],
    )
    assert previa.valido
    assert previa.despacho == despachar(time=[BULBASAUR, CHARMANDER], carga=[POCAO])


def test_previa_devolve_o_motivo_em_vez_de_levantar():
    previa = prever_despacho(
        treinador=treinador(),
        time=[],
        grafo=KANTO,
        visitados=SO_PALLET,
        destino=ROUTE_1,
        seed=SEED,
        agora=AGORA,
    )
    assert not previa.valido
    assert previa.despacho is None
    assert previa.codigo == "TIME_VAZIO"
    assert "nenhum Pokemon" in (previa.motivo or "")


def test_previa_traduz_o_destino_fora_de_alcance():
    previa = prever_despacho(
        treinador=treinador(),
        time=[BULBASAUR],
        grafo=KANTO,
        visitados=SO_PALLET,
        destino=MT_MOON,
        seed=SEED,
        agora=AGORA,
    )
    assert previa.codigo == "DESTINO_FORA_DE_ALCANCE"
    assert previa.detalhes["proximo_passo_id"] == "route-1"


def test_previa_de_local_inexistente_continua_sendo_404():
    with pytest.raises(LocalDesconhecido):
        prever_despacho(
            treinador=treinador(),
            time=[BULBASAUR],
            grafo=KANTO,
            visitados=SO_PALLET,
            destino=LocalDaExpedicao("saffron-city", 10, 14, 6),
            seed=SEED,
            agora=AGORA,
        )


# --- Estado observado -------------------------------------------------------

ETA = datetime(2026, 11, 6, 12, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("agora", "esperado"),
    [
        (ETA - timedelta(hours=1), EstadoObservado.EM_CURSO),
        (ETA - timedelta(seconds=1), EstadoObservado.EM_CURSO),
        (ETA - timedelta(microseconds=1), EstadoObservado.EM_CURSO),
        (ETA, EstadoObservado.AGUARDANDO_RELATORIO),
        (ETA + timedelta(microseconds=1), EstadoObservado.AGUARDANDO_RELATORIO),
        (ETA + timedelta(days=30), EstadoObservado.AGUARDANDO_RELATORIO),
    ],
)
def test_estado_observado_nos_limites_do_eta(agora: datetime, esperado: EstadoObservado) -> None:
    assert estado_observado(StatusExpedicao.EM_CURSO, ETA, agora) == esperado


@pytest.mark.parametrize(
    "status",
    [
        StatusExpedicao.CONCLUIDA_SUCESSO,
        StatusExpedicao.CONCLUIDA_FALHA,
        StatusExpedicao.ABORTADA,
    ],
)
def test_status_terminal_ignora_o_eta(status: StatusExpedicao) -> None:
    assert estado_observado(status, ETA, ETA - timedelta(hours=1)) == EstadoObservado(status.value)
    assert estado_observado(status, ETA, ETA + timedelta(hours=1)) == EstadoObservado(status.value)


def test_estado_observado_aceita_o_texto_da_coluna():
    assert estado_observado("EM_CURSO", ETA, ETA) == EstadoObservado.AGUARDANDO_RELATORIO
    assert estado_observado("ABORTADA", ETA, ETA) == EstadoObservado.ABORTADA


def test_status_desconhecido_e_recusado():
    with pytest.raises(ErroDeDominio):
        estado_observado("VOANDO", ETA, AGORA)


def test_aguardando_relatorio_nao_e_valor_de_coluna():
    """A coluna continua EM_CURSO ate a Fase 7 escrever o resultado."""
    assert "AGUARDANDO_RELATORIO" not in {status.value for status in StatusExpedicao}
    assert EstadoObservado.AGUARDANDO_RELATORIO.precisa_de_resolucao
    assert not EstadoObservado.EM_CURSO.precisa_de_resolucao
    assert not EstadoObservado.AGUARDANDO_RELATORIO.terminal
    assert EstadoObservado.ABORTADA.terminal


def test_fusos_diferentes_descrevem_o_mesmo_instante():
    brasilia = timezone(timedelta(hours=-3))
    mesmo_instante = ETA.astimezone(brasilia)
    assert estado_observado(StatusExpedicao.EM_CURSO, ETA, mesmo_instante) == (
        EstadoObservado.AGUARDANDO_RELATORIO
    )
    um_segundo_antes = mesmo_instante - timedelta(seconds=1)
    assert estado_observado(StatusExpedicao.EM_CURSO, ETA, um_segundo_antes) == (
        EstadoObservado.EM_CURSO
    )


@pytest.mark.parametrize("nome", ["eta", "agora"])
def test_estado_observado_recusa_relogio_sem_fuso(nome: str) -> None:
    ingenuo = ETA.replace(tzinfo=None)
    argumentos = {"eta": ETA, "agora": ETA}
    argumentos[nome] = ingenuo
    with pytest.raises(RelogioSemFuso) as recusa:
        estado_observado(StatusExpedicao.EM_CURSO, **argumentos)
    assert recusa.value.detalhes["parametro"] == nome


# --- Tempo restante ---------------------------------------------------------


@pytest.mark.parametrize(
    ("agora", "esperado"),
    [
        (ETA - timedelta(minutes=30), 1800),
        (ETA - timedelta(seconds=1), 1),
        (ETA - timedelta(microseconds=1), 1),  # sobra fracao: falta um segundo
        (ETA - timedelta(milliseconds=1500), 2),
        (ETA, 0),
        (ETA + timedelta(microseconds=1), 0),
        (ETA + timedelta(days=365), 0),
    ],
)
def test_tabela_de_tempo_restante(agora: datetime, esperado: int) -> None:
    assert tempo_restante(ETA, agora) == esperado


@pytest.mark.parametrize(
    "deslocamento",
    [
        timedelta(days=-400),
        timedelta(seconds=-1),
        timedelta(microseconds=-1),
        timedelta(0),
        timedelta(microseconds=1),
        timedelta(seconds=1),
        timedelta(days=400),
    ],
)
def test_tempo_restante_nunca_e_negativo(deslocamento: timedelta) -> None:
    assert tempo_restante(ETA, ETA + deslocamento) >= 0


@pytest.mark.parametrize(
    "deslocamento",
    [
        timedelta(hours=-5),
        timedelta(seconds=-1),
        timedelta(microseconds=-1),
        timedelta(0),
        timedelta(microseconds=1),
        timedelta(seconds=90),
    ],
)
def test_zero_restante_acontece_exatamente_quando_a_expedicao_acabou(
    deslocamento: timedelta,
) -> None:
    """Contador em zero e 'em curso' na mesma resposta seria contradicao visivel."""
    agora = ETA + deslocamento
    acabou = estado_observado(StatusExpedicao.EM_CURSO, ETA, agora) == (
        EstadoObservado.AGUARDANDO_RELATORIO
    )
    assert (tempo_restante(ETA, agora) == 0) is acabou


def test_tempo_restante_recusa_relogio_sem_fuso():
    with pytest.raises(RelogioSemFuso):
        tempo_restante(ETA, ETA.replace(tzinfo=None))


def test_tempo_restante_de_uma_expedicao_recem_despachada():
    despacho = despachar()
    assert tempo_restante(despacho.eta, despacho.started_at) == despacho.duracao_minutos * 60


# --- Determinismo (Artigo III) ----------------------------------------------


def test_duas_chamadas_iguais_produzem_o_mesmo_despacho():
    primeiro = despachar(time=[BULBASAUR, CHARMANDER], carga=[POCAO, POKEBOLA])
    segundo = despachar(time=[BULBASAUR, CHARMANDER], carga=[POCAO, POKEBOLA])
    assert primeiro == segundo


def test_dificuldade_e_chance_nao_mudam_entre_chamadas():
    for _ in range(3):
        assert dificuldade_do_local(MT_MOON) == 47.5
        assert chance_estimada(47.5, 47.5) == 0.5


def test_a_ordem_dos_visitados_nao_muda_o_despacho():
    visitados = ("pallet-town", "route-1", "viridian-city")
    um = despachar(destino=VIRIDIAN, visitados=visitados)
    outro = despachar(destino=VIRIDIAN, visitados=tuple(reversed(visitados)))
    assert um == outro


def test_o_despacho_e_imutavel():
    despacho = despachar()
    with pytest.raises(AttributeError):
        despacho.duracao_minutos = 1  # type: ignore[misc]
