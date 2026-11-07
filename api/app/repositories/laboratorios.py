"""Acesso a tabela `laboratorios`.

A constraint unique em `professor_id` e como a regra 5 da spec 002 ("cada
conta tem exatamente um laboratorio") vira regra de banco.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Laboratorio

NIVEL_INICIAL = 1
EXPERIENCIA_INICIAL = 0
MOEDAS_INICIAIS = 0


def criar(sessao: Session, *, professor_id: uuid.UUID, nome: str) -> Laboratorio:
    """Cria o laboratorio nivel 1, zero experiencia e zero moedas (regra 6)."""
    laboratorio = Laboratorio(
        professor_id=professor_id,
        nome=nome,
        nivel=NIVEL_INICIAL,
        experiencia=EXPERIENCIA_INICIAL,
        moedas=MOEDAS_INICIAIS,
        starters_concedidos=False,
    )
    sessao.add(laboratorio)
    sessao.flush()
    return laboratorio


def buscar_por_professor_id(sessao: Session, professor_id: uuid.UUID) -> Laboratorio | None:
    return sessao.scalar(select(Laboratorio).where(Laboratorio.professor_id == professor_id))


def buscar_por_id(sessao: Session, laboratorio_id: uuid.UUID) -> Laboratorio | None:
    return sessao.get(Laboratorio, laboratorio_id)


def travar_para_concessao(sessao: Session, laboratorio_id: uuid.UUID) -> Laboratorio | None:
    """Trava a linha do laboratorio ate o fim da transacao (Artigo VII).

    Sem o lock, duas concessoes concorrentes sobre o MESMO laboratorio leem
    `starters_concedidos = False` as duas e as duas seguem em frente. A unique
    de `professor_id` protege o caminho do registro, mas nao protege uma
    segunda chamada a concessao sobre um laboratorio que ja existe.

    `populate_existing=True` pela mesma razao de `travar` abaixo: o unico
    chamador (`auth_service._conceder_kit`) recebe o laboratorio logo depois
    de `laboratorios_repo.criar` adiciona-lo a sessao, entao ele ja esta no
    identity map quando este `SELECT ... FOR UPDATE` roda. Hoje isso e
    inofensivo — a linha acabou de nascer nesta mesma transacao, com um id novo
    que nenhuma outra transacao pode ter visto antes do commit, entao nao ha
    escritor concorrente cujo resultado este SELECT precise enxergar — mas
    seria um bug silencioso esperando um segundo chamador que travar sobre um
    laboratorio JA EXISTENTE. `populate_existing` custa nada e evita essa
    armadilha para sempre.
    """
    return sessao.scalar(
        select(Laboratorio)
        .where(Laboratorio.id == laboratorio_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def marcar_starters_concedidos(sessao: Session, laboratorio: Laboratorio) -> None:
    """Invariante 10 do SDD 3.3: os starters sao concedidos exatamente uma vez."""
    laboratorio.starters_concedidos = True


def travar(sessao: Session, laboratorio_id: uuid.UUID) -> Laboratorio | None:
    """Trava a linha do laboratorio ate o fim da transacao (Artigo VII).

    A resolucao de expedicao credita experiencia de laboratorio (spec 007,
    regra 14); sem o lock, duas expedicoes do mesmo laboratorio resolvendo ao
    mesmo tempo poderiam ler a mesma `experiencia` de partida e uma das duas
    ganancias se perderia.

    `populate_existing=True` nao e cosmetico aqui, e a correcao do bug: TODA
    rota autenticada passa por `professor_atual` (`core/dependencias.py`), que
    ja carregou este MESMO `Laboratorio` na sessao da requisicao antes de
    qualquer lock ser pedido. Sem `populate_existing`, o SQLAlchemy encontra o
    objeto no identity map, devolve ele tal como estava, e NAO sobrescreve os
    atributos com o que acabou de vir do `SELECT ... FOR UPDATE` — a trava na
    linha e real, mas os valores que o chamador enxerga sao os de antes dela.
    Com tres `claim`s concorrentes do mesmo laboratorio, os tres liam
    `experiencia` e `nivel` de partida iguais e so a ultima escrita vencia: as
    outras duas experiencias eram jogadas fora em silencio. Reproduzido com
    `threading.Barrier(3)` contra o compose antes desta correcao.
    """
    return sessao.scalar(
        select(Laboratorio)
        .where(Laboratorio.id == laboratorio_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def atualizar_progressao(laboratorio: Laboratorio, *, nivel: int, experiencia: int) -> None:
    """Grava o nivel e a experiencia que `game.laboratorio` ja calculou."""
    laboratorio.nivel = nivel
    laboratorio.experiencia = experiencia


def creditar_moedas(laboratorio: Laboratorio, quantidade: int) -> None:
    """Soma `quantidade` ao saldo do laboratorio (conclusao de entrega, spec 008).

    So soma: quem decidiu quanto e `game.delivery.recompensa_da_entrega`, e
    quem chama precisa ja ter travado a linha (`travar`, acima) na mesma
    transacao — duas conclusoes concorrentes do mesmo laboratorio, sem o lock,
    perderiam um credito exatamente como duas expedicoes concorrentes
    perderiam experiencia (ver o comentario de `travar`).
    """
    laboratorio.moedas += quantidade


def atualizar_sorteio_entregas(laboratorio: Laboratorio, sorteado_em: datetime) -> None:
    """Carimba o instante do ultimo sorteio da Central (invariantes 15 e 19).

    Chamada tanto quando a Central REGERA a lista valida (`POST
    /deliveries/refresh` com `vagas_para_repor == 0`) quanto quando REPOE uma
    vaga aberta por expiracao ou aceite (`vagas_para_repor > 0`) — as duas sao
    sorteio de verdade (`game.delivery.gerar_pedidos`), e o intervalo conta
    "desde o ultimo sorteio" (regra 19), nao so desde o ultimo descarte.

    A UNICA excecao e o sorteio de bootstrap, quando `entregas_geradas_em`
    ainda e nulo (laboratorio que nunca abriu a Central): esse primeiro
    carimbo so acontece no proprio descarte, nunca na reposicao — e e por
    isso que o chamador de reposicao (`services/entregas.py::refresh`) so
    invoca esta funcao quando ja havia um carimbo anterior. Sem essa
    distincao, o PRIMEIRO preenchimento (lista vazia, criterio 13) carimbaria
    o relogio e a PROXIMA chamada — que descarta essa lista recem-cheia,
    criterio 21 — passaria a exigir os 15 minutos que "o primeiro sorteio nao
    e descarte de nada" promete nao cobrar.

    Em nenhum dos dois casos isso faz o REPOR em si esperar (invariante 18):
    esta funcao so GRAVA o carimbo, nunca o LE para decidir se a reposicao
    pode prosseguir — quem le o carimbo para decidir e so o caminho do
    descarte, em `services/entregas.py::refresh`.
    """
    laboratorio.entregas_geradas_em = sorteado_em
