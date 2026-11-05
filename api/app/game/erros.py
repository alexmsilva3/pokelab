"""Excecoes do dominio.

Artigo VI: os invariantes da secao 3.3 do SDD sao impostos aqui, nao no router
nem na constraint de banco. Quem chama recebe uma excecao de dominio com
mensagem em portugues, e a camada de servico decide como ela vira resposta HTTP.
"""


# N818 pede sufixo "Error"; o Artigo X manda nomear o dominio em portugues.
class ErroDeDominio(Exception):  # noqa: N818
    """Regra de jogo violada. Raiz de toda excecao de app/game/."""


class CurvaDesconhecida(ErroDeDominio):
    """A curva de crescimento informada nao e uma das quatro do SDD 4.1."""


class NivelInvalido(ErroDeDominio):
    """Nivel fora da faixa de 1 ate NIVEL_MAXIMO (invariante 7)."""


class ExperienciaInvalida(ErroDeDominio):
    """Experiencia acumulada negativa."""


class AvatarInvalido(ErroDeDominio):
    """A semente do avatar nao permite derivar iniciais."""


class KitInicialInvalido(ErroDeDominio):
    """A entrada do kit inicial nao corresponde ao que balance.py declara."""
