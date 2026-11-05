"""Excecoes da camada de aplicacao.

Diferente de `app.game.erros`, que guarda violacao de regra de jogo, este
modulo guarda erro de autenticacao, conflito e escopo — o vocabulario de
`services/` e `routers/`. O handler unico de `main.py` traduz qualquer
`ErroDeAplicacao` para o envelope padrao da skill pokelab-api-conventions:

    {"erro": {"codigo": "...", "mensagem": "...", "detalhes": {...}}}
"""

from __future__ import annotations

from typing import Any, ClassVar


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
