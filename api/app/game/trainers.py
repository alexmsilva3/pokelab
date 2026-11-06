"""O treinador: geracao, status e progressao (questao 16 e SDD 4.1).

O avatar nao tem asset. Ele e um dado estrutural — iniciais e uma cor — que o
frontend desenha. Isso evita versionar 40 imagens para um NPC que existe para
ser despachado, e deixa a identidade visual do treinador estavel sem depender
de arquivo nenhum.

A cor sai de um digest blake2b da semente, nunca de `hash()`: o hash embutido
do Python e randomizado por processo, e um avatar que muda de cor a cada
reinicio da API nao e identidade visual, e sim bug intermitente.

A curva de nivel do treinador e quadratica e bem mais lenta que a de um
Pokemon. Ela mora aqui, e nao junto da curva do laboratorio, apesar de as duas
terem a mesma forma `base * (n - 1)^2`: o que elas compartilham e tres linhas
de aritmetica, e o que as separa e tudo o mais — vocabulario de erro proprio,
teto proprio (o treinador satura em NIVEL_MAXIMO, o laboratorio nao tem teto) e
calibragem que vai divergir na Fase 9, quando a progressao do professor e a do
treinador forem afinadas uma contra a outra. Um helper comum parametrizado por
base, teto e classe de excecao custaria mais indirecao do que as linhas que
economiza.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from hashlib import blake2b
from math import floor, isqrt
from typing import Final

from app.game import balance
from app.game.aleatoriedade import GeradorAleatorio
from app.game.erros import AvatarInvalido, ErroDeDominio, ExperienciaInvalida

# Nomes curtos e, quando possivel, neutros de genero: o professor contrata
# pessoas, e a ficha nao precisa decidir isso por elas.
NOMES_DE_TREINADOR: Final[tuple[str, ...]] = (
    "Alex",
    "Ariel",
    "Bento",
    "Cam",
    "Casey",
    "Charlie",
    "Dani",
    "Eli",
    "Enzo",
    "Frankie",
    "Gabi",
    "Hiro",
    "Isa",
    "Ivo",
    "Jamie",
    "Jordan",
    "Juno",
    "Kai",
    "Kenji",
    "Lari",
    "Lee",
    "Lou",
    "Luca",
    "Mika",
    "Milo",
    "Morgan",
    "Nico",
    "Noa",
    "Ollie",
    "Pat",
    "Quinn",
    "Rafa",
    "Remy",
    "Rio",
    "Robin",
    "Sam",
    "Sasha",
    "Theo",
    "Toni",
    "Val",
    "Yuki",
    "Zuri",
)

# Paleta fechada em vez de cor livre do digest: tom aleatorio em HSL produz
# combinacoes ilegiveis com texto branco. Todas estas aguentam a inicial por
# cima.
PALETA_AVATAR: Final[tuple[str, ...]] = (
    "#1f7a3f",
    "#2563a8",
    "#7a2f6b",
    "#a8471f",
    "#3f4a8c",
    "#8c6a1f",
    "#1f7a74",
    "#8c2f3f",
    "#4a7a1f",
    "#5c3fa8",
    "#a8551f",
    "#2f6b8c",
)


class NivelDeTreinadorInvalido(ErroDeDominio):
    """O nivel do treinador esta fora da faixa de 1 a NIVEL_MAXIMO."""


class StatusTreinador(StrEnum):
    """Os quatro estados do treinador (SDD 3.2), nos mesmos nomes da coluna."""

    DISPONIVEL = "DISPONIVEL"
    EM_EXPEDICAO = "EM_EXPEDICAO"
    EM_ENTREGA = "EM_ENTREGA"
    DESCANSANDO = "DESCANSANDO"

    @property
    def ocupado(self) -> bool:
        """Invariante 3 do SDD 3.3: so expedicao e entrega travam o treinador.

        `DESCANSANDO` nao e ocupado. O treinador voltou, esta no laboratorio e
        o professor pode remontar o time dele — o descanso adia a proxima
        missao, nao a arrumacao do time.
        """
        return self in (StatusTreinador.EM_EXPEDICAO, StatusTreinador.EM_ENTREGA)


# Como cada status aparece numa mensagem de erro dirigida ao professor.
DESCRICAO_DO_STATUS: Final[dict[StatusTreinador, str]] = {
    StatusTreinador.DISPONIVEL: "disponivel",
    StatusTreinador.EM_EXPEDICAO: "em expedicao",
    StatusTreinador.EM_ENTREGA: "em entrega",
    StatusTreinador.DESCANSANDO: "descansando",
}


@dataclass(frozen=True, slots=True)
class Avatar:
    """Identidade visual de um treinador, sem arquivo."""

    iniciais: str
    cor: str

    def para_dicionario(self) -> dict[str, str]:
        """Forma serializavel, que e como o avatar e guardado e devolvido."""
        return {"iniciais": self.iniciais, "cor": self.cor}


@dataclass(frozen=True, slots=True)
class TreinadorGerado:
    """O que o dominio sabe dizer sobre um treinador novo antes de ele existir."""

    nome: str
    avatar: Avatar


def gerar_nome(rng: GeradorAleatorio) -> str:
    """Sorteia um nome de treinador do gerador semeado recebido."""
    return rng.choice(NOMES_DE_TREINADOR)


def _digestao(semente: str) -> int:
    digest = blake2b(semente.encode("utf-8"), digest_size=balance.BYTES_DIGEST_AVATAR).digest()
    return int.from_bytes(digest, "big")


def _iniciais(semente: str) -> str:
    palavras = [palavra for palavra in semente.split() if palavra[:1].isalpha()]
    if not palavras:
        raise AvatarInvalido(f"Nao ha letra nenhuma na semente do avatar: {semente!r}.")
    if len(palavras) > 1:
        letras = palavras[0][:1] + palavras[-1][:1]
    else:
        letras = palavras[0][: balance.LETRAS_INICIAIS_AVATAR]
    return letras.upper()


def gerar_avatar(semente: str) -> Avatar:
    """Deriva iniciais e cor de uma semente textual, de forma estavel.

    A semente e tipicamente o nome do treinador. Duas chamadas com a mesma
    semente devolvem o mesmo avatar, em qualquer processo e em qualquer dia.
    """
    if not semente.strip():
        raise AvatarInvalido("A semente do avatar nao pode ser vazia.")
    cor = PALETA_AVATAR[_digestao(semente) % len(PALETA_AVATAR)]
    return Avatar(iniciais=_iniciais(semente), cor=cor)


def gerar_treinador(rng: GeradorAleatorio) -> TreinadorGerado:
    """Nome sorteado e avatar derivado dele."""
    nome = gerar_nome(rng)
    return TreinadorGerado(nome=nome, avatar=gerar_avatar(nome))


# --- Status ----------------------------------------------------------------


def status_de(valor: str | StatusTreinador) -> StatusTreinador:
    """Converte o texto gravado na coluna em status, recusando o que nao reconhece."""
    try:
        return StatusTreinador(valor)
    except ValueError:
        nomes = ", ".join(status.value for status in StatusTreinador)
        raise ErroDeDominio(
            f"Status de treinador desconhecido: {valor!r}. Esperado um de: {nomes}."
        ) from None


# --- Progressao (SDD 4.1) ---------------------------------------------------

NIVEL_MINIMO_TREINADOR: Final[int] = 1


def exigir_nivel_de_treinador(nivel: int) -> None:
    """Faixa valida do nivel do treinador, imposta no dominio (Artigo VI)."""
    if nivel < NIVEL_MINIMO_TREINADOR or nivel > balance.NIVEL_MAXIMO:
        raise NivelDeTreinadorInvalido(
            f"Nivel de treinador {nivel} fora da faixa valida de "
            f"{NIVEL_MINIMO_TREINADOR} a {balance.NIVEL_MAXIMO}."
        )


def experiencia_total_para_nivel(nivel: int) -> int:
    """Experiencia acumulada para o treinador ESTAR neste nivel.

    O SDD 4.1 escreve a curva como `EXP_TREINADOR_BASE * n^2`; aqui ela aparece
    deslocada em um nivel, pelo mesmo motivo de `laboratorio.py` e das curvas de
    Pokemon: o nivel 1 custa zero. Um treinador recem-chegado nao pode nascer
    devendo experiencia.
    """
    exigir_nivel_de_treinador(nivel)
    return balance.EXP_TREINADOR_BASE * (nivel - 1) ** 2


def nivel_para_experiencia(experiencia: int) -> int:
    """O inverso, saturando em NIVEL_MAXIMO.

    Inverter `base * (n - 1)^2` e uma raiz quadrada inteira, exata e em tempo
    constante: `isqrt` evita tanto o erro de `math.sqrt` quanto o laco que
    percorreria a tabela nivel a nivel.
    """
    if experiencia < 0:
        raise ExperienciaInvalida(f"Experiencia acumulada nao pode ser negativa: {experiencia}.")
    nivel = isqrt(experiencia // balance.EXP_TREINADOR_BASE) + NIVEL_MINIMO_TREINADOR
    return min(nivel, balance.NIVEL_MAXIMO)


def experiencia_para_o_proximo_nivel(experiencia: int) -> int | None:
    """Quanto falta para subir, ou None quando ja esta no nivel maximo.

    None e nao zero: zero diria que falta nada, isto e, que a proxima
    experiencia faz subir. Mesmo contrato que `PokemonDetalhe` ja usava, para
    que as duas fichas nao mintam de maneiras diferentes.
    """
    nivel = nivel_para_experiencia(experiencia)
    if nivel >= balance.NIVEL_MAXIMO:
        return None
    return experiencia_total_para_nivel(nivel + 1) - experiencia


# A constante de balance e float porque um terco nao tem forma decimal exata.
# `limit_denominator()` recupera o racional pretendido (1/3, e nao a dizima
# truncada que `Fraction(str(...))` produziria), e a conta segue exata.
_FRACAO_DO_TREINADOR: Final[Fraction] = Fraction(balance.FRACAO_EXP_TREINADOR).limit_denominator()


def experiencia_ganha_por_batalha(experiencia_total_da_batalha: int) -> int:
    """A parte do treinador numa batalha vencida (SDD 4.1).

    A base e a experiencia TOTAL que a batalha gerou, antes da divisao entre os
    Pokemon do time: assim o treinador progride no mesmo ritmo levando um ou
    tres. O tamanho do time e escolha tatica do professor e nao deveria ser
    tambem um imposto sobre a carreira do treinador.

    Arredonda para baixo, que e o unico sentido que nunca cria experiencia do
    nada. Quem aplica isso e a Fase 7; aqui fica so o contrato.
    """
    if experiencia_total_da_batalha < 0:
        raise ExperienciaInvalida(
            f"A experiencia da batalha nao pode ser negativa: {experiencia_total_da_batalha}."
        )
    return floor(experiencia_total_da_batalha * _FRACAO_DO_TREINADOR)
