"""Resolucao da expedicao: o laco, os eventos e o contrato de ordem (spec 007).

Os dois testes que importam mais estao no topo e sao os que nao podem ser
afrouxados: o determinismo por semente (criterio 3, Artigo III) e a ORDEM DAS
ROLAGENS fixada no plano da spec 007. O segundo existe para quebrar
ruidosamente no dia em que alguem inserir um sorteio no meio do laco — porque
nesse dia o resultado de toda expedicao ja despachada e ainda nao resolvida
muda, e nenhum outro teste acusaria.
"""

from uuid import UUID, uuid4

import pytest

from app.game import balance
from app.game.encounter import LinhaDeEncontro
from app.game.expedition import (
    ContextoDeResolucao,
    ContextoInvalido,
    DestinoEmCampo,
    EspecieEmCampo,
    LocalDaExpedicao,
    PokemonDaExpedicao,
    StatusExpedicao,
    TimeVazio,
    TipoDeEvento,
    TreinadorEmCampo,
    chance_estimada,
    experiencia_de_laboratorio,
    minuto_do_encontro,
    resolver,
)
from app.game.experience import experiencia_total_para_nivel
from app.game.itens import CategoriaDeItem, ItemDaMochila
from tests.geradores_falsos import GeradorRoteirizado, GeradorSemeado

# --- Catalogo de teste ------------------------------------------------------
#
# Numeros do seed de Kanto, com duas excecoes marcadas caso a caso: uma especie
# com `experiencia_base` zero, para isolar o efeito do desgaste na chance, e
# uma com `experiencia_base` absurda, para forcar a cadeia de evolucao inteira
# dentro de uma unica batalha.

BULBASAUR = EspecieEmCampo(
    id=1,
    nome="Bulbasaur",
    experiencia_base=64,
    taxa_captura=45,
    curva_crescimento="media_lenta",
    soma_stats_base=318,
    evolui_para_id=2,
    evolui_em_nivel=16,
)
IVYSAUR = EspecieEmCampo(
    id=2,
    nome="Ivysaur",
    experiencia_base=142,
    taxa_captura=45,
    curva_crescimento="media_lenta",
    soma_stats_base=405,
    evolui_para_id=3,
    evolui_em_nivel=32,
)
VENUSAUR = EspecieEmCampo(
    id=3,
    nome="Venusaur",
    experiencia_base=263,
    taxa_captura=45,
    curva_crescimento="media_lenta",
    soma_stats_base=525,
)
CATERPIE = EspecieEmCampo(
    id=10,
    nome="Caterpie",
    experiencia_base=39,
    taxa_captura=255,
    curva_crescimento="media_rapida",
    soma_stats_base=195,
)
PIDGEY = EspecieEmCampo(
    id=16,
    nome="Pidgey",
    experiencia_base=50,
    taxa_captura=255,
    curva_crescimento="media_lenta",
    soma_stats_base=251,
)

CATALOGO = {especie.id: especie for especie in (BULBASAUR, IVYSAUR, VENUSAUR, CATERPIE, PIDGEY)}

POKE_BALL = ItemDaMochila(
    item_id="poke-ball",
    nome="Poke Ball",
    categoria=CategoriaDeItem.POKEBOLA,
    potencia=1.0,
    quantidade=10,
)
POTION = ItemDaMochila(
    item_id="potion",
    nome="Potion",
    categoria=CategoriaDeItem.CURA,
    potencia=20.0,
    quantidade=1,
)

TREINADOR = TreinadorEmCampo(id=UUID(int=7), nome="Ash", nivel=1)


def bolsa_de_bolas(quantidade: int) -> ItemDaMochila:
    """Uma carga de Poke Ball com exatamente a municao que o teste quer gastar.

    `POKE_BALL` traz dez unidades de proposito — e a carga folgada da maioria
    dos testes. Os testes de limite precisam do contrario: so com a municao
    curta da para separar "acabou a bola" de "acabou a vaga na bagagem", que
    sao os dois limites distintos da regra 10 da spec 007.
    """
    return ItemDaMochila(
        item_id="poke-ball",
        nome="Poke Ball",
        categoria=CategoriaDeItem.POKEBOLA,
        potencia=1.0,
        quantidade=quantidade,
    )


def membro(especie: EspecieEmCampo, nivel: int, hp_atual_pct: int = 100) -> PokemonDaExpedicao:
    """Um Pokemon do time com nivel e experiencia ja coerentes entre si.

    A coerencia nao e detalhe de teste: `aplicar_experiencia` recusa um
    Pokemon cujo nivel nao corresponda a experiencia gravada, e e assim que o
    dominio impede que uma captura mal gravada estoure na expedicao seguinte.
    """
    return PokemonDaExpedicao(
        id=uuid4(),
        especie_id=especie.id,
        nivel=nivel,
        experiencia=experiencia_total_para_nivel(especie.curva_crescimento, nivel),
        hp_atual_pct=hp_atual_pct,
    )


def contexto(
    *,
    time=None,
    linhas=((10, 5, 5),),
    carga=(POKE_BALL,),
    encontros_base=3,
    nivel_dificuldade=3,
    especies_vistas=frozenset(),
    duracao_minutos=30,
    nivel_treinador=1,
    catalogo=None,
) -> ContextoDeResolucao:
    """Um contexto completo, com o minimo que cada teste precisa trocar.

    `linhas` chega como `(especie_id, nivel_min, nivel_max)` com peso 1: o peso
    so importa nos testes de sorteio ponderado, que moram em
    `test_game_encounter.py`.
    """
    faixas = tuple(
        LinhaDeEncontro(especie_id=especie_id, peso=1, nivel_min=minimo, nivel_max=maximo)
        for especie_id, minimo, maximo in linhas
    )
    return ContextoDeResolucao(
        treinador=TreinadorEmCampo(id=TREINADOR.id, nome=TREINADOR.nome, nivel=nivel_treinador),
        time=tuple(time if time is not None else (membro(BULBASAUR, 10),)),
        destino=DestinoEmCampo(
            local=LocalDaExpedicao(
                id="viridian-forest",
                nivel_selvagem_min=min(linha.nivel_min for linha in faixas),
                nivel_selvagem_max=max(linha.nivel_max for linha in faixas),
                nivel_dificuldade=nivel_dificuldade,
            ),
            nome="Viridian Forest",
            encontros_base=encontros_base,
            linhas_de_encontro=faixas,
        ),
        origem_nome="Pallet Town",
        catalogo=catalogo if catalogo is not None else CATALOGO,
        carga=tuple(carga),
        especies_vistas=frozenset(especies_vistas),
        nomes_de_itens={"poke-ball": "Poke Ball", "great-ball": "Great Ball", "potion": "Potion"},
        duracao_minutos=duracao_minutos,
    )


def roteiro(floats, inteiros) -> GeradorRoteirizado:
    return GeradorRoteirizado(floats=floats, inteiros=inteiros)


def tipos(relatorio) -> list[str]:
    return [evento.tipo.value for evento in relatorio.eventos]


# --- 1. Determinismo (criterio 3, Artigo III) -------------------------------


def test_a_mesma_semente_produz_o_mesmo_relatorio():
    ctx = contexto(
        time=(membro(BULBASAUR, 12), membro(CATERPIE, 8)),
        linhas=((10, 3, 7), (16, 4, 8)),
        encontros_base=5,
    )

    primeiro = resolver(ctx, GeradorSemeado(20261106))
    segundo = resolver(ctx, GeradorSemeado(20261106))

    assert primeiro == segundo


def test_a_mesma_semente_produz_os_mesmos_textos_na_mesma_ordem():
    ctx = contexto(encontros_base=4, linhas=((10, 3, 7), (16, 4, 8)))

    primeiro = resolver(ctx, GeradorSemeado(99))
    segundo = resolver(ctx, GeradorSemeado(99))

    assert [(e.ordem, e.tipo, e.texto, e.ocorrido_em_minuto) for e in primeiro.eventos] == [
        (e.ordem, e.tipo, e.texto, e.ocorrido_em_minuto) for e in segundo.eventos
    ]
    assert [e.payload for e in primeiro.eventos] == [e.payload for e in segundo.eventos]


def test_sementes_diferentes_produzem_relatorios_diferentes():
    # Sem isto, uma resolucao que ignorasse o gerador passaria no teste de
    # determinismo com louvor.
    ctx = contexto(
        time=(membro(BULBASAUR, 10),),
        linhas=((10, 3, 9), (16, 3, 9)),
        encontros_base=6,
    )

    relatorios = {
        tuple(evento.texto for evento in resolver(ctx, GeradorSemeado(semente)).eventos)
        for semente in range(8)
    }

    assert len(relatorios) > 1


# --- 2. A ordem das rolagens e contrato -------------------------------------


def test_a_ordem_das_rolagens_segue_o_plano_na_vitoria():
    # Vitoria com achado e com tentativa de captura: o caso que consome todas
    # as oito rolagens do plano da spec 007, na ordem.
    gerador = roteiro(floats=[0.0, 0.0, 0.0, 0.0, 0.0], inteiros=[0, 5, 3])

    resolver(contexto(encontros_base=1), gerador)

    assert gerador.chamadas == [
        "randint(-1,1)",  # 1 quantidade de encontros
        "random",  # 2 especie
        "randint(5,5)",  # 3 nivel do selvagem
        "random",  # 4 vitoria
        "randint(3,8)",  # 5 desgaste da vitoria
        "random",  # 6 houve achado
        "random",  # 7 qual item
        "random",  # 8 tentativa de captura
    ]


def test_a_ordem_das_rolagens_segue_o_plano_na_derrota():
    gerador = roteiro(floats=[0.0, 0.99], inteiros=[0, 5, 20])

    resolver(contexto(encontros_base=1), gerador)

    assert gerador.chamadas == [
        "randint(-1,1)",  # 1 quantidade de encontros
        "random",  # 2 especie
        "randint(5,5)",  # 3 nivel do selvagem
        "random",  # 4 derrota
        "randint(15,30)",  # 5' desgaste da derrota
    ]


def test_sem_achado_a_rolagem_do_item_nao_acontece():
    # A rolagem 7 e condicional; a 6 nao. Trocar isso dessincroniza toda
    # semente gravada.
    gerador = roteiro(floats=[0.0, 0.0, 0.99, 0.0], inteiros=[0, 5, 3])

    resolver(contexto(encontros_base=1), gerador)

    assert gerador.chamadas.count("random") == 4


def test_sem_bola_na_carga_a_rolagem_da_captura_nao_acontece():
    gerador = roteiro(floats=[0.0, 0.0, 0.99], inteiros=[0, 5, 3])

    resolver(contexto(encontros_base=1, carga=()), gerador)

    assert gerador.chamadas == [
        "randint(-1,1)",
        "random",
        "randint(5,5)",
        "random",
        "randint(3,8)",
        "random",
    ]


# --- 3. Partida, retorno e linha do tempo (criterio 1) ----------------------


def test_a_linha_do_tempo_comeca_em_partida_e_termina_em_retorno():
    relatorio = resolver(contexto(encontros_base=3), GeradorSemeado(5))

    assert relatorio.eventos[0].tipo is TipoDeEvento.PARTIDA
    assert relatorio.eventos[0].ocorrido_em_minuto == 0
    assert relatorio.eventos[-1].tipo is TipoDeEvento.RETORNO
    assert [evento.ordem for evento in relatorio.eventos] == list(range(len(relatorio.eventos)))


def test_o_texto_da_partida_nomeia_treinador_origem_e_destino():
    relatorio = resolver(contexto(), GeradorSemeado(5))

    texto = relatorio.eventos[0].texto
    assert "Ash" in texto
    assert "Pallet Town" in texto
    assert "Viridian Forest" in texto


def test_nenhum_texto_passa_do_limite_da_coluna():
    relatorio = resolver(contexto(encontros_base=7), GeradorSemeado(321))

    assert all(len(evento.texto) <= balance.LIMITE_TEXTO_DO_EVENTO for evento in relatorio.eventos)
    assert all(evento.texto.endswith(".") for evento in relatorio.eventos)


def test_os_minutos_distribuem_os_encontros_entre_a_partida_e_o_retorno():
    assert [minuto_do_encontro(60, indice, 3) for indice in range(3)] == [15, 30, 45]


def test_na_falha_o_treinador_volta_antes_do_fim_da_duracao():
    gerador = roteiro(floats=[0.0, 0.99] * 3, inteiros=[0, 5, 20, 5, 20, 5, 20])

    relatorio = resolver(
        contexto(encontros_base=6, carga=(), duracao_minutos=70, nivel_dificuldade=10),
        gerador,
    )

    assert relatorio.status is StatusExpedicao.CONCLUIDA_FALHA
    assert relatorio.eventos[-1].ocorrido_em_minuto < 70
    assert relatorio.duracao_efetiva_minutos < 70


# --- 4. Falha por tres derrotas sem cura (criterio 15) ----------------------


def test_tres_derrotas_sem_cura_encerram_a_expedicao_em_falha():
    gerador = roteiro(floats=[0.0, 0.99] * 3, inteiros=[0, 5, 20, 5, 20, 5, 20])

    relatorio = resolver(contexto(encontros_base=6, nivel_dificuldade=10), gerador)

    assert relatorio.status is StatusExpedicao.CONCLUIDA_FALHA
    assert relatorio.derrotas == balance.DERROTAS_PARA_FALHAR
    assert relatorio.encontros == balance.DERROTAS_PARA_FALHAR
    assert relatorio.capturas == ()
    assert relatorio.desbloqueia_destino is False
    assert relatorio.experiencia_laboratorio == 0
    # O laco parou: as rolagens dos encontros 4, 5 e 6 nao foram consumidas.
    assert gerador.floats == []
    assert gerador.inteiros == []


def test_a_falha_mantem_a_experiencia_ganha_antes_da_derrota():
    # Uma vitoria e depois tres derrotas: a regra 16 da spec 007 manda manter
    # o que foi ganho em campo.
    gerador = roteiro(
        floats=[0.0, 0.0, 0.99, 0.99] + [0.0, 0.99] * 3,
        inteiros=[0, 5, 3, 5, 20, 5, 20, 5, 20],
    )

    relatorio = resolver(contexto(encontros_base=4, nivel_dificuldade=10), gerador)

    assert relatorio.status is StatusExpedicao.CONCLUIDA_FALHA
    assert relatorio.vitorias == 1
    assert relatorio.experiencia_treinador > 0
    assert relatorio.time[0].experiencia_ganha > 0


def test_a_falha_nao_traz_as_capturas_e_o_retorno_explica():
    # Uma captura no primeiro encontro e depois tres derrotas sem cura: a
    # regra 16 da spec 007 manda voltar de maos vazias, e o texto do retorno
    # precisa dizer isso para que o evento CAPTURA na linha do tempo nao
    # pareca contradizer o resumo.
    gerador = roteiro(
        floats=[0.0, 0.0, 0.99, 0.0] + [0.0, 0.99] * 3,
        inteiros=[0, 5, 3, 5, 20, 5, 20, 5, 20],
    )

    relatorio = resolver(contexto(encontros_base=4, nivel_dificuldade=10), gerador)

    assert relatorio.status is StatusExpedicao.CONCLUIDA_FALHA
    assert TipoDeEvento.CAPTURA.value in tipos(relatorio)
    assert relatorio.capturas == ()
    retorno = relatorio.eventos[-1]
    assert retorno.payload["capturas_perdidas"] == 1
    assert retorno.payload["capturas"] == 0
    assert "ficou para tras" in retorno.texto
    # A bola foi arremessada e continua gasta.
    assert relatorio.itens_consumidos[0].item_id == "poke-ball"


def test_o_retorno_da_falha_conta_as_derrotas_sem_cura_e_nao_o_total():
    # Quatro derrotas, a primeira curada: a expedicao acabou na terceira
    # seguida sem Pocao, e e esse o numero que explica a volta.
    gerador = roteiro(floats=[0.0, 0.99] * 4, inteiros=[0, 5, 20, 5, 20, 5, 20, 5, 20])

    relatorio = resolver(contexto(encontros_base=5, carga=(POTION,), nivel_dificuldade=10), gerador)

    assert relatorio.derrotas == 4
    assert relatorio.eventos[-1].payload["derrotas_sem_cura"] == balance.DERROTAS_PARA_FALHAR
    assert "3 derrotas seguidas" in relatorio.eventos[-1].texto


# --- 5. Cura em campo (criterio 16) -----------------------------------------


def test_a_pocao_e_consumida_e_a_contagem_de_derrotas_recomeca():
    gerador = roteiro(floats=[0.0, 0.99] * 3, inteiros=[0, 5, 20, 5, 20, 5, 20])

    relatorio = resolver(contexto(encontros_base=3, carga=(POTION,), nivel_dificuldade=10), gerador)

    assert relatorio.derrotas == 3
    # Tres derrotas, mas a primeira consumiu a Pocao e zerou a contagem.
    assert relatorio.status is StatusExpedicao.CONCLUIDA_SUCESSO
    assert relatorio.itens_consumidos == (
        type(relatorio.itens_consumidos[0])(item_id="potion", nome="Potion", quantidade=1),
    )
    contratempos = [e for e in relatorio.eventos if e.tipo is TipoDeEvento.CONTRATEMPO]
    assert contratempos[0].payload["item_usado"] == "potion"
    assert contratempos[0].payload["derrotas_sem_cura"] == 0
    assert "Potion" in contratempos[0].texto
    assert contratempos[1].payload["item_usado"] is None


def test_a_cura_devolve_pontos_de_vida_ao_time():
    gerador = roteiro(floats=[0.0, 0.99], inteiros=[0, 5, 30])

    relatorio = resolver(contexto(encontros_base=1, carga=(POTION,), nivel_dificuldade=10), gerador)

    # 100 - 30 de desgaste + 20 da Pocao.
    assert relatorio.time[0].hp_depois_pct == 90


# --- 6. Bagagem, bolas e captura (criterios 6, 7 e 8) -----------------------


def test_a_bagagem_cheia_limita_as_capturas_e_nao_impede_o_registro():
    # Time de tres: a bagagem comporta 6 - 3 = 3 capturas. Todas as rolagens
    # em zero fazem toda captura dar certo.
    time = (membro(BULBASAUR, 20), membro(CATERPIE, 20), membro(PIDGEY, 20))
    gerador = roteiro(floats=[0.0] * 40, inteiros=[0] + [5, 3] * 8)

    relatorio = resolver(contexto(time=time, encontros_base=7), gerador)

    assert relatorio.encontros == 7
    assert len(relatorio.capturas) == balance.CAPACIDADE_TOTAL_TREINADOR - len(time)
    assert relatorio.avistamentos[0].vezes == 7
    assert len([e for e in relatorio.eventos if e.tipo is TipoDeEvento.CAPTURA]) == 3


def test_toda_bola_da_carga_e_arremessada_quando_a_bagagem_comporta():
    # Time de tres (bagagem 3) com exatamente tres bolas: os dois limites da
    # regra 10 se encostam, e nenhum dos dois pode cortar o terceiro
    # arremesso. Descontar a bola gasta duas vezes — uma dentro do calculo do
    # limite e outra na comparacao com as capturas ja feitas — deixaria a
    # ultima bola na mochila, sem CAPTURA nem CAPTURA_FALHA.
    time = (membro(BULBASAUR, 20), membro(CATERPIE, 20), membro(PIDGEY, 20))
    gerador = roteiro(floats=[0.0] * 20, inteiros=[0] + [5, 3] * 3)

    relatorio = resolver(contexto(time=time, encontros_base=3, carga=(bolsa_de_bolas(3),)), gerador)

    assert relatorio.vitorias == 3
    assert len(relatorio.capturas) == 3
    assert len([e for e in relatorio.eventos if e.tipo is TipoDeEvento.CAPTURA]) == 3
    assert relatorio.itens_consumidos[0].item_id == "poke-ball"
    assert relatorio.itens_consumidos[0].quantidade == 3


def test_a_municao_limita_as_capturas_quando_a_bagagem_sobra():
    # Time de um: a bagagem comporta 6 - 1 = 5, e quem corta e a bola. O SDD
    # 4.6 manda min(2, 5) = 2 capturas em cinco encontros vencidos.
    gerador = roteiro(floats=[0.0] * 30, inteiros=[0] + [5, 3] * 5)

    relatorio = resolver(contexto(encontros_base=5, carga=(bolsa_de_bolas(2),)), gerador)

    assert relatorio.vitorias == 5
    assert len(relatorio.capturas) == 2
    assert relatorio.itens_consumidos[0].quantidade == 2
    assert relatorio.avistamentos[0].vezes == 5


def test_a_bagagem_limita_as_capturas_quando_a_municao_sobra():
    # Dez bolas para uma bagagem de tres: aqui quem corta e a bagagem, e os
    # dois encontros seguintes continuam virando avistamento (regra 11).
    time = (membro(BULBASAUR, 20), membro(CATERPIE, 20), membro(PIDGEY, 20))
    gerador = roteiro(floats=[0.0] * 30, inteiros=[0] + [5, 3] * 5)

    relatorio = resolver(
        contexto(time=time, encontros_base=5, carga=(bolsa_de_bolas(10),)), gerador
    )

    assert relatorio.encontros == 5
    assert len(relatorio.capturas) == 3
    assert relatorio.itens_consumidos[0].quantidade == 3
    assert relatorio.avistamentos[0].vezes == 5


def test_carga_sem_pokebola_nao_captura_e_continua_registrando():
    gerador = roteiro(floats=[0.0] * 40, inteiros=[0] + [5, 3] * 6)

    relatorio = resolver(contexto(encontros_base=5, carga=()), gerador)

    assert relatorio.capturas == ()
    assert relatorio.itens_consumidos == ()
    assert relatorio.avistamentos[0].vezes == 5
    assert TipoDeEvento.CAPTURA.value not in tipos(relatorio)
    assert TipoDeEvento.CAPTURA_FALHA.value not in tipos(relatorio)


def test_a_bola_e_consumida_na_falha_da_captura():
    # Captura com rolagem acima da chance: a bola foi gasta do mesmo jeito.
    gerador = roteiro(floats=[0.0, 0.0, 0.99, 0.99], inteiros=[0, 5, 3])

    relatorio = resolver(contexto(encontros_base=1), gerador)

    assert relatorio.capturas == ()
    assert relatorio.itens_consumidos[0].item_id == "poke-ball"
    assert relatorio.itens_consumidos[0].quantidade == 1
    assert TipoDeEvento.CAPTURA_FALHA.value in tipos(relatorio)


def test_o_capturado_chega_com_nivel_experiencia_e_vida_coerentes():
    gerador = roteiro(floats=[0.0, 0.0, 0.99, 0.0], inteiros=[0, 6, 3])

    relatorio = resolver(contexto(encontros_base=1, linhas=((10, 6, 6),)), gerador)

    captura = relatorio.capturas[0]
    assert captura.especie_id == CATERPIE.id
    assert captura.nivel == 6
    assert captura.experiencia == experiencia_total_para_nivel(CATERPIE.curva_crescimento, 6)
    assert captura.hp_atual_pct == balance.BASE_PERCENTUAL


# --- 7. A chance cai conforme o time se desgasta ----------------------------


def test_a_chance_do_ultimo_encontro_e_menor_que_a_do_primeiro():
    # A especie enfrentada tem experiencia base zero para isolar o efeito: sem
    # ganho de nivel, a unica coisa que move o poder do time e o hp.
    sem_experiencia = EspecieEmCampo(
        id=10,
        nome="Caterpie",
        experiencia_base=0,
        taxa_captura=255,
        curva_crescimento="media_rapida",
        soma_stats_base=195,
    )
    gerador = roteiro(floats=[0.0, 0.0, 0.99] * 6, inteiros=[0] + [5, 8] * 6)

    relatorio = resolver(
        contexto(
            encontros_base=6,
            carga=(),
            catalogo=dict(CATALOGO) | {sem_experiencia.id: sem_experiencia},
            linhas=((10, 5, 5),),
        ),
        gerador,
    )

    batalhas = [e for e in relatorio.eventos if e.tipo is TipoDeEvento.BATALHA]
    assert len(batalhas) == 6
    assert batalhas[-1].payload["chance"] < batalhas[0].payload["chance"]
    assert relatorio.time[0].hp_depois_pct == 100 - 8 * 6


def test_time_inteiro_nocauteado_nao_divide_por_zero_e_cai_no_piso():
    nocauteado = (membro(BULBASAUR, 10, hp_atual_pct=0),)
    gerador = roteiro(floats=[0.0, 0.99], inteiros=[0, 5, 20])

    relatorio = resolver(contexto(time=nocauteado, encontros_base=1, carga=()), gerador)

    contratempo = relatorio.eventos[-2]
    assert contratempo.payload["poder_time"] == 0
    # A sigmoide com razao zero vale 1/(1+e^2.5), que ainda esta acima do piso
    # de 5%: o time derrubado nao perde a chance remota de vencer, e nada aqui
    # dividiu por zero.
    assert contratempo.payload["chance"] == chance_estimada(0.0, contratempo.payload["dificuldade"])
    assert contratempo.payload["chance"] >= balance.P_VITORIA_MINIMA


# --- 8. Experiencia, nivel e evolucao (criterios 9, 10, 11 e 12) ------------


def test_cada_pokemon_leva_a_parcela_e_o_treinador_leva_um_terco_do_total():
    time = (membro(BULBASAUR, 10), membro(PIDGEY, 10))
    gerador = roteiro(floats=[0.0, 0.0, 0.99, 0.99], inteiros=[0, 5, 3])

    relatorio = resolver(contexto(time=time, encontros_base=1), gerador)

    # Caterpie nivel 5: 39 * 5 // 7 = 27. Cada um leva 27 // 2 = 13; o
    # treinador leva 27 // 3 = 9, calculado sobre o TOTAL.
    batalha = next(e for e in relatorio.eventos if e.tipo is TipoDeEvento.BATALHA)
    assert batalha.payload["exp_da_batalha"] == 27
    assert batalha.payload["exp_por_pokemon"] == 13
    assert [membro_final.experiencia_ganha for membro_final in relatorio.time] == [13, 13]
    assert relatorio.experiencia_treinador == 9


def test_o_nocauteado_conta_como_participante_na_divisao():
    time = (membro(BULBASAUR, 10), membro(PIDGEY, 10, hp_atual_pct=0))
    gerador = roteiro(floats=[0.0, 0.0, 0.99, 0.99], inteiros=[0, 5, 3])

    relatorio = resolver(contexto(time=time, encontros_base=1), gerador)

    assert relatorio.time[1].experiencia_ganha == 13


def test_subir_de_nivel_gera_evento_com_o_nivel_novo():
    gerador = roteiro(floats=[0.0, 0.0, 0.99, 0.99] * 3, inteiros=[0] + [5, 3] * 3)

    relatorio = resolver(contexto(time=(membro(CATERPIE, 3),), encontros_base=3), gerador)

    subidas = [e for e in relatorio.eventos if e.tipo is TipoDeEvento.SUBIU_NIVEL]
    assert subidas
    assert subidas[-1].payload["nivel_depois"] == relatorio.time[0].nivel_depois
    assert relatorio.time[0].nivel_depois > relatorio.time[0].nivel_antes


def test_o_nivel_100_nao_e_ultrapassado_e_o_excedente_e_descartado():
    teto = experiencia_total_para_nivel(BULBASAUR.curva_crescimento, balance.NIVEL_MAXIMO)
    campeao = PokemonDaExpedicao(
        id=uuid4(),
        especie_id=BULBASAUR.id,
        nivel=balance.NIVEL_MAXIMO,
        experiencia=teto,
        hp_atual_pct=100,
    )
    gerador = roteiro(floats=[0.0, 0.0, 0.99, 0.99] * 2, inteiros=[0] + [5, 3] * 2)

    relatorio = resolver(contexto(time=(campeao,), encontros_base=2), gerador)

    assert relatorio.time[0].nivel_depois == balance.NIVEL_MAXIMO
    assert relatorio.time[0].experiencia_depois == teto
    assert relatorio.time[0].experiencia_ganha == 0
    assert TipoDeEvento.SUBIU_NIVEL.value not in tipos(relatorio)


def test_a_cadeia_de_evolucao_inteira_cabe_numa_expedicao():
    # Experiencia base absurda de proposito: o salto do nivel 15 ao 33 numa
    # unica batalha e o que faz a cadeia encadear (SDD 4.1).
    monstro = EspecieEmCampo(
        id=10,
        nome="Caterpie",
        experiencia_base=50_000,
        taxa_captura=255,
        curva_crescimento="media_rapida",
        soma_stats_base=195,
    )
    catalogo = dict(CATALOGO) | {monstro.id: monstro}
    gerador = roteiro(floats=[0.0, 0.0, 0.99, 0.99], inteiros=[0, 5, 3])

    relatorio = resolver(
        contexto(
            time=(membro(BULBASAUR, 15),),
            encontros_base=1,
            catalogo=catalogo,
        ),
        gerador,
    )

    evolucoes = [e for e in relatorio.eventos if e.tipo is TipoDeEvento.EVOLUCAO]
    assert [evento.payload["especie_nome"] for evento in evolucoes] == ["Ivysaur", "Venusaur"]
    assert relatorio.time[0].evoluiu_para_id == VENUSAUR.id
    assert relatorio.time[0].especie_final_id == VENUSAUR.id
    assert relatorio.time[0].especie_id == BULBASAUR.id
    assert "evoluiu" in evolucoes[0].texto


def test_a_evolucao_muda_o_poder_do_time_no_encontro_seguinte():
    monstro = EspecieEmCampo(
        id=10,
        nome="Caterpie",
        experiencia_base=50_000,
        taxa_captura=255,
        curva_crescimento="media_rapida",
        soma_stats_base=195,
    )
    catalogo = dict(CATALOGO) | {monstro.id: monstro}
    gerador = roteiro(floats=[0.0, 0.0, 0.99, 0.99] * 2, inteiros=[0] + [5, 3] * 2)

    relatorio = resolver(
        contexto(time=(membro(BULBASAUR, 15),), encontros_base=2, catalogo=catalogo),
        gerador,
    )

    batalhas = [e for e in relatorio.eventos if e.tipo is TipoDeEvento.BATALHA]
    assert batalhas[1].payload["poder_time"] > batalhas[0].payload["poder_time"]


# --- 9. Pokedex: avistamento e descoberta (criterios 17 e 18) ---------------


def test_toda_especie_enfrentada_entra_nos_avistamentos():
    gerador = roteiro(floats=[0.0] * 40, inteiros=[0] + [5, 3] * 6)

    relatorio = resolver(contexto(encontros_base=5, linhas=((10, 5, 5),), carga=()), gerador)

    assert [avistado.especie_id for avistado in relatorio.avistamentos] == [CATERPIE.id]
    assert relatorio.avistamentos[0].vezes == 5
    assert relatorio.avistamentos[0].primeira_vez is True


def test_a_descoberta_acontece_uma_unica_vez_por_especie():
    gerador = roteiro(floats=[0.0] * 40, inteiros=[0] + [5, 3] * 5)

    relatorio = resolver(contexto(encontros_base=4, carga=()), gerador)

    assert tipos(relatorio).count(TipoDeEvento.DESCOBERTA.value) == 1


def test_especie_ja_vista_nao_gera_descoberta():
    gerador = roteiro(floats=[0.0] * 40, inteiros=[0] + [5, 3] * 4)

    relatorio = resolver(
        contexto(encontros_base=3, carga=(), especies_vistas={CATERPIE.id}), gerador
    )

    assert TipoDeEvento.DESCOBERTA.value not in tipos(relatorio)
    assert relatorio.avistamentos[0].vezes == 3
    assert relatorio.avistamentos[0].primeira_vez is False


# --- 10. Achados e experiencia do laboratorio (criterio 14) -----------------


def test_o_achado_entra_no_relatorio_com_nome_e_quantidade():
    gerador = roteiro(floats=[0.0, 0.0, 0.0, 0.0, 0.99], inteiros=[0, 5, 3])

    relatorio = resolver(contexto(encontros_base=1, nivel_dificuldade=5), gerador)

    achado = relatorio.itens_encontrados[0]
    assert achado.item_id == "poke-ball"
    assert achado.nome == "Poke Ball"
    # Dificuldade 5: 1 + 5 // 4 = 2 unidades.
    assert achado.quantidade == 2
    evento = next(e for e in relatorio.eventos if e.tipo is TipoDeEvento.ITEM)
    assert "Poke Ball" in evento.texto


@pytest.mark.parametrize(
    ("dificuldade", "esperado"),
    [(1, 120), (3, 160), (5, 200), (10, 300)],
)
def test_a_experiencia_do_laboratorio_cresce_com_a_dificuldade(dificuldade, esperado):
    assert experiencia_de_laboratorio(dificuldade) == esperado


def test_so_o_sucesso_paga_o_laboratorio():
    gerador = roteiro(floats=[0.0, 0.0, 0.99, 0.99], inteiros=[0, 5, 3])

    sucesso = resolver(contexto(encontros_base=1, nivel_dificuldade=5), gerador)

    assert sucesso.status is StatusExpedicao.CONCLUIDA_SUCESSO
    assert sucesso.experiencia_laboratorio == experiencia_de_laboratorio(5)
    assert sucesso.desbloqueia_destino is True


# --- 11. Invariantes do contexto (Artigo VI) --------------------------------


def test_expedicao_sem_time_nao_resolve():
    # Invariante 17: erro proprio, e nao o generico, porque o professor precisa
    # ler "monte o time dele antes de despachar".
    with pytest.raises(TimeVazio):
        contexto(time=(), encontros_base=1)


def test_especie_fora_do_catalogo_e_recusada_na_entrada():
    with pytest.raises(ContextoInvalido) as erro:
        contexto(linhas=((999, 5, 5),))

    assert "999" in str(erro.value)


def test_evolucao_que_troca_a_curva_e_recusada_na_entrada():
    # Nivel e experiencia sao o mesmo numero lido de dois jeitos: trocar a
    # curva na evolucao faria o Pokemon gravado nao conferir com a propria
    # especie na expedicao seguinte.
    torto = EspecieEmCampo(
        id=1,
        nome="Bulbasaur",
        experiencia_base=64,
        taxa_captura=45,
        curva_crescimento="rapida",
        soma_stats_base=318,
        evolui_para_id=2,
        evolui_em_nivel=16,
    )
    with pytest.raises(ContextoInvalido) as erro:
        contexto(catalogo={torto.id: torto, IVYSAUR.id: IVYSAUR, CATERPIE.id: CATERPIE})

    assert "curvas de crescimento diferentes" in str(erro.value)


def test_duracao_negativa_e_recusada():
    with pytest.raises(ContextoInvalido):
        contexto(duracao_minutos=-1)


def test_o_mesmo_pokemon_duas_vezes_no_time_e_recusado():
    repetido = membro(BULBASAUR, 10)
    with pytest.raises(ContextoInvalido):
        contexto(time=(repetido, repetido))


# --- 12. Propriedades sobre varias sementes ---------------------------------


@pytest.mark.parametrize("semente", range(12))
def test_propriedades_que_valem_para_qualquer_semente(semente):
    ctx = contexto(
        time=(membro(BULBASAUR, 12), membro(CATERPIE, 9)),
        linhas=((10, 3, 8), (16, 4, 9)),
        encontros_base=6,
        carga=(POKE_BALL, POTION),
    )

    relatorio = resolver(ctx, GeradorSemeado(semente))

    assert relatorio.status in (
        StatusExpedicao.CONCLUIDA_SUCESSO,
        StatusExpedicao.CONCLUIDA_FALHA,
    )
    assert relatorio.encontros == relatorio.vitorias + relatorio.derrotas
    assert len(relatorio.capturas) <= balance.CAPACIDADE_TOTAL_TREINADOR - len(ctx.time)
    assert sum(avistado.vezes for avistado in relatorio.avistamentos) == relatorio.encontros
    for final in relatorio.time:
        assert 1 <= final.nivel_depois <= balance.NIVEL_MAXIMO
        assert final.nivel_depois >= final.nivel_antes
        assert 0 <= final.hp_depois_pct <= balance.BASE_PERCENTUAL
        assert final.experiencia_ganha >= 0
    for consumido in relatorio.itens_consumidos:
        assert consumido.quantidade > 0
    for evento in relatorio.eventos:
        assert evento.ocorrido_em_minuto >= 0
        assert len(evento.texto) <= balance.LIMITE_TEXTO_DO_EVENTO
    for batalha in relatorio.eventos:
        if batalha.payload and "chance" in batalha.payload:
            assert balance.P_VITORIA_MINIMA <= batalha.payload["chance"] <= balance.P_VITORIA_MAXIMA
