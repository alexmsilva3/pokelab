"""Excecoes da camada de aplicacao.

Diferente de `app.game.erros`, que guarda violacao de regra de jogo, este
modulo guarda erro de autenticacao, conflito e escopo — o vocabulario de
`services/` e `routers/`. O handler unico de `main.py` traduz qualquer
`ErroDeAplicacao` para o envelope padrao da skill pokelab-api-conventions:

    {"erro": {"codigo": "...", "mensagem": "...", "detalhes": {...}}}
"""

from __future__ import annotations

from typing import Any, ClassVar

from app.game.delivery import ErroDeEntrega as _ErroDeEntregaNoDominio
from app.game.expedition import ErroDeExpedicao as _ErroDeExpedicaoNoDominio
from app.game.mapa import DestinoForaDeAlcance as _DestinoForaDeAlcanceNoDominio
from app.game.mapa import LocalDesconhecido as _LocalDesconhecidoNoDominio
from app.game.soltar import ErroDeSoltura as _ErroDeSolturaNoDominio
from app.game.team import ErroDeTime
from app.game.viveiro import ErroDeViveiro as _ErroDeViveiroNoDominio


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


# --- Fase 8: viveiro, soltura e Central de Entregas (spec 008) --------------


class ConflitoDeViveiro(ErroDeAplicacao):
    """Traduz uma recusa de `game.viveiro` para 409 (regra 4 da spec 008).

    Hoje so existe uma: `ViveiroTransbordado`, levantada pela guarda do
    `game.viveiro` dentro do servico de despacho (tarefa 15) e em lugar
    nenhum mais. O `codigo` vem do proprio erro de dominio
    (VIVEIRO_TRANSBORDADO), nunca de uma tabela de traducao aqui — mesmo
    raciocinio de `ConflitoDeTime` e `ConflitoDeExpedicao`.
    """

    status_code: ClassVar[int] = 409

    def __init__(self, erro: _ErroDeViveiroNoDominio) -> None:
        self.codigo = erro.codigo
        super().__init__(str(erro), detalhes=erro.detalhes)


class ConflitoDeSoltura(ErroDeAplicacao):
    """Traduz uma recusa de `game.soltar` para 409 (`DELETE /pokemon/{id}`).

    O `codigo` vem do proprio erro de dominio (POKEMON_EM_EXPEDICAO,
    TREINADOR_OCUPADO, POKEMON_COMPROMETIDO, ULTIMO_POKEMON, ...). O aceite de
    entrega (tarefa 13) reusa a MESMA traducao para `exigir_que_sobre_pokemon`,
    porque e a mesma guarda do dominio (invariante 25) vista de dois
    endpoints diferentes.
    """

    status_code: ClassVar[int] = 409

    def __init__(self, erro: _ErroDeSolturaNoDominio) -> None:
        self.codigo = erro.codigo
        super().__init__(str(erro), detalhes=erro.detalhes)


class ConflitoDeEntrega(ErroDeAplicacao):
    """Traduz uma recusa de `game.delivery` para 409 (rotas de `/deliveries`).

    O `codigo` vem do proprio erro de dominio (POKEMON_NAO_ATENDE_AO_PEDIDO,
    SEM_ESPECIE_CANDIDATA, ...), mesmo raciocinio de `ConflitoDeTime`.
    """

    status_code: ClassVar[int] = 409

    def __init__(self, erro: _ErroDeEntregaNoDominio) -> None:
        self.codigo = erro.codigo
        super().__init__(str(erro), detalhes=erro.detalhes)


class EntregaExpirada(ErroDeAplicacao):
    """O pedido venceu antes do aceite (criterio 20 da spec 008).

    Nao vem de `game.delivery` porque a comparacao com o estado observado e
    feita no servico, que e quem tem o relogio em maos (Artigo I): o dominio
    so EXPOE `estado_observado_entrega`, nao decide o que fazer com o
    resultado.
    """

    status_code: ClassVar[int] = 409
    codigo: ClassVar[str] = "ENTREGA_EXPIRADA"
    mensagem_padrao: ClassVar[str] = "Este pedido venceu e nao pode mais ser aceito."


class EntregaNaoDisponivel(ErroDeAplicacao):
    """O pedido nao esta mais `DISPONIVEL` por outro motivo que nao o prazo.

    Cobre aceitar um pedido que ja esta `EM_CURSO`, `CONCLUIDA` ou
    `DESCARTADA` — raro no uso normal (a tela nao oferece o botao), mas a
    segunda linha de defesa do Artigo VI nao pode confiar so na interface.
    """

    status_code: ClassVar[int] = 409
    codigo: ClassVar[str] = "ENTREGA_NAO_DISPONIVEL"
    mensagem_padrao: ClassVar[str] = "Este pedido nao esta mais disponivel para aceite."


class TreinadorOcupadoParaEntrega(ErroDeAplicacao):
    """O treinador escolhido para a entrega nao esta `DISPONIVEL` (regra 20).

    Mesmo `codigo` de `team.TreinadorOcupado`: e o mesmo vocabulario do
    contrato desde a Fase 4, e o professor nao precisa de um segundo nome
    para "este treinador esta ocupado".
    """

    status_code: ClassVar[int] = 409
    codigo: ClassVar[str] = "TREINADOR_OCUPADO"
    mensagem_padrao: ClassVar[str] = "Este treinador esta ocupado e nao pode sair em entrega."


class PokemonIndisponivel(ErroDeAplicacao):
    """Um Pokemon escolhido para a entrega nao esta livre no viveiro (regra 20).

    Cobre quem esta num time, em expedicao, ja comprometido com OUTRA entrega,
    ou que simplesmente nao pertence a este laboratorio — o professor nunca
    distingue estes casos pela resposta (mesmo raciocinio de
    `RecursoNaoEncontrado`), so pelo `pokemon_id` em `detalhes`.
    """

    status_code: ClassVar[int] = 409
    codigo: ClassVar[str] = "POKEMON_INDISPONIVEL"
    mensagem_padrao: ClassVar[str] = "Um ou mais Pokemon escolhidos nao estao livres no viveiro."


class EntregaEmCurso(ErroDeAplicacao):
    """O prazo da entrega ainda nao venceu (`POST /deliveries/{id}/claim`).

    Mesmo papel de `ExpedicaoEmCurso`: pedir a conclusao antes do `eta` e
    recusado com o motivo, nao com um resultado vazio.
    """

    status_code: ClassVar[int] = 409
    codigo: ClassVar[str] = "ENTREGA_EM_CURSO"
    mensagem_padrao: ClassVar[str] = (
        "O prazo desta entrega ainda nao venceu; a conclusao so existe depois que ela volta."
    )


class AguardeParaRegerar(ErroDeAplicacao):
    """Invariante 15: regerar a lista inteira exige o intervalo (regra 19).

    So e levantada quando NAO ha vaga a repor (`vagas_para_repor == 0`):
    repor o que venceu ou foi aceito e de graca (invariante 23), e e esse o
    caso em que `POST /deliveries/refresh` nunca cai aqui.
    """

    status_code: ClassVar[int] = 409
    codigo: ClassVar[str] = "AGUARDE_PARA_REGERAR"
    mensagem_padrao: ClassVar[str] = "A lista de entregas ainda nao pode ser descartada."
