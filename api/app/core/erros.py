"""Excecoes da camada de aplicacao.

Diferente de `app.game.erros`, que guarda violacao de regra de jogo, este
modulo guarda erro de autenticacao, conflito e escopo — o vocabulario de
`services/` e `routers/`. O handler unico de `main.py` traduz qualquer
`ErroDeAplicacao` para o envelope padrao da skill pokelab-api-conventions:

    {"erro": {"codigo": "...", "mensagem": "...", "detalhes": {...}}}
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.game.expedition import ErroDeExpedicao as _ErroDeExpedicaoNoDominio
from app.game.mapa import DestinoForaDeAlcance as _DestinoForaDeAlcanceNoDominio
from app.game.mapa import LocalDesconhecido as _LocalDesconhecidoNoDominio
from app.game.team import ErroDeTime


# N818 pede sufixo "Error"; o Artigo X manda nomear o dominio da aplicacao em
# portugues, como ja decidido em app.game.erros.ErroDeDominio.
class ErroDeAplicacao(Exception):  # noqa: N818
    """Erro conhecido da aplicacao, com status HTTP e codigo ja decididos."""

    status_code: ClassVar[int] = 400
    codigo: ClassVar[str] = "ERRO_DE_APLICACAO"
    mensagem_padrao: ClassVar[str] = "Nao foi possivel completar a operacao."

    def __init__(
        self, mensagem: str | None = None, *, detalhes: dict[str, Any] | None = None
    ) -> None:
        self.mensagem = mensagem or self.mensagem_padrao
        self.detalhes = detalhes
        super().__init__(self.mensagem)


class NaoAutenticado(ErroDeAplicacao):
    """Sem token, token malformado, assinatura invalida ou token expirado.

    Os quatro casos produzem a mesma excecao de proposito: quem chama uma rota
    protegida sem sessao valida nao precisa, e nao deveria, distinguir qual
    deles aconteceu.
    """

    status_code: ClassVar[int] = 401
    codigo: ClassVar[str] = "NAO_AUTENTICADO"
    mensagem_padrao: ClassVar[str] = "Sessao ausente, invalida ou expirada."


class CredenciaisInvalidas(ErroDeAplicacao):
    """Usuario inexistente ou senha errada — a mesma resposta para os dois.

    Regra 10 da spec 002: nao revelar qual dos dois casos aconteceu.
    """

    status_code: ClassVar[int] = 401
    codigo: ClassVar[str] = "CREDENCIAIS_INVALIDAS"
    mensagem_padrao: ClassVar[str] = "Usuario ou senha incorretos."


class UsuarioEmUso(ErroDeAplicacao):
    """O nome de usuario normalizado ja pertence a outra conta."""

    status_code: ClassVar[int] = 409
    codigo: ClassVar[str] = "USUARIO_EM_USO"
    mensagem_padrao: ClassVar[str] = "Este nome de usuario ja esta em uso."


class RecursoNaoEncontrado(ErroDeAplicacao):
    """O recurso nao existe, ou existe e pertence a outro laboratorio.

    As duas situacoes respondem igual (404, nunca 403): um professor nao deve
    conseguir distinguir "nao existe" de "nao e seu" inspecionando a resposta.
    """

    status_code: ClassVar[int] = 404
    codigo: ClassVar[str] = "RECURSO_NAO_ENCONTRADO"
    mensagem_padrao: ClassVar[str] = "O recurso solicitado nao existe."


class KitJaConcedido(ErroDeAplicacao):
    """Invariante 10: o kit inicial ja foi concedido a este laboratorio."""

    status_code = 409
    codigo = "KIT_JA_CONCEDIDO"
    mensagem_padrao = "Este laboratorio ja recebeu os Pokemon iniciais."


class ConflitoDeTime(ErroDeAplicacao):
    """Traduz um `ErroDeTime` de `game/team.py` para o envelope 409.

    O `codigo` vem do proprio erro de dominio (TIME_CHEIO, POKEMON_JA_ATRIBUIDO,
    TREINADOR_OCUPADO, POKEMON_COMPROMETIDO, POKEMON_DUPLICADO, ...) em vez de
    uma tabela de traducao aqui: o contrato de API ja mora em `game/team.py`
    (plan.md), e duplica-lo neste modulo e so uma forma de deixar os dois
    divergirem num refactor futuro.
    """

    status_code: ClassVar[int] = 409

    def __init__(self, erro: ErroDeTime) -> None:
        self.codigo = erro.codigo
        super().__init__(str(erro), detalhes=erro.detalhes)


class LocalNaoEncontrado(ErroDeAplicacao):
    """Traduz `game.mapa.LocalDesconhecido` para 404 (criterio 10 da spec 005).

    O mapa so le, entao este e o unico `ErroDeMapa` que esta rota pode
    levantar: `GrafoInvalido`, `DestinoForaDeAlcance` e
    `ParametroDeDuracaoInvalido` ou sao bug de seed, ou pertencem ao despacho
    de expedicao que a Fase 6 implementa.
    """

    status_code: ClassVar[int] = 404

    def __init__(self, erro: _LocalDesconhecidoNoDominio) -> None:
        self.codigo = erro.codigo
        super().__init__(str(erro), detalhes=erro.detalhes)


class ConflitoDeExpedicao(ErroDeAplicacao):
    """Traduz uma recusa de `game.expedition.calcular_despacho` para 409.

    O `codigo` vem do proprio erro de dominio (TREINADOR_OCUPADO, TIME_VAZIO,
    DESTINO_FORA_DE_ALCANCE, ESTOQUE_INSUFICIENTE, CARGA_INVALIDA, ...), nunca
    de uma tabela de traducao aqui — mesmo raciocinio de `ConflitoDeTime`.
    `DestinoForaDeAlcance` vem de `game.mapa`, nao de `game.expedition`: o
    invariante 6 e imposto la, e a Fase 6 reusa a excecao em vez de duplicar o
    invariante.
    """

    status_code: ClassVar[int] = 409

    def __init__(self, erro: _ErroDeExpedicaoNoDominio | _DestinoForaDeAlcanceNoDominio) -> None:
        self.codigo = erro.codigo
        super().__init__(str(erro), detalhes=erro.detalhes)


class ExpedicaoEmCurso(ErroDeAplicacao):
    """O prazo da expedicao ainda nao venceu (criterio 2 da spec 007).

    `POST /expeditions/{id}/claim` so resolve depois que o `eta` passou; pedir
    o relatorio antes disso e recusado com o motivo, e nao com um relatorio
    vazio.
    """

    status_code: ClassVar[int] = 409
    codigo: ClassVar[str] = "EXPEDICAO_EM_CURSO"
    mensagem_padrao: ClassVar[str] = (
        "O prazo desta expedicao ainda nao venceu; o relatorio so existe depois que ela volta."
    )


class ExpedicaoAbortada(ErroDeAplicacao):
    """A expedicao foi abortada e nunca produziu relatorio (spec 007).

    Diferente de uma expedicao concluida (sucesso ou falha), o aborto nao
    passa pela resolucao: nao ha linha do tempo, nao ha capturas, nao ha o que
    reler.
    """

    status_code: ClassVar[int] = 409
    codigo: ClassVar[str] = "EXPEDICAO_ABORTADA"
    mensagem_padrao: ClassVar[str] = "Esta expedicao foi abortada e nao tem relatorio de campo."


class ExpedicaoNaoEstaEmCurso(ErroDeAplicacao):
    """A expedicao nao esta `EM_CURSO` no momento do aborto (criterio 12 da spec 006).

    Cobre tanto quem ja terminou de verdade (concluida ou abortada) quanto
    quem so esta `AGUARDANDO_RELATORIO`: o `eta` ja passou, a missao acabou
    na pratica, e abortar uma expedicao que ja terminou nao interrompe nada —
    so apagaria a chance de a Fase 7 gerar o relatorio dela. Decisao
    registrada aqui porque a spec fala em abortar "em andamento", e isto
    deixou de ser andamento.
    """

    status_code: ClassVar[int] = 409
    codigo: ClassVar[str] = "EXPEDICAO_NAO_ESTA_EM_CURSO"
    mensagem_padrao: ClassVar[str] = (
        "Esta expedicao ja nao esta em curso e por isso nao pode ser abortada."
    )
