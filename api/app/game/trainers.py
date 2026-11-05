"""Geracao de treinadores: nome e avatar (questao 16 do SDD).

O avatar nao tem asset. Ele e um dado estrutural — iniciais e uma cor — que o
frontend desenha. Isso evita versionar 40 imagens para um NPC que existe para
ser despachado, e deixa a identidade visual do treinador estavel sem depender
de arquivo nenhum.

A cor sai de um digest blake2b da semente, nunca de `hash()`: o hash embutido
do Python e randomizado por processo, e um avatar que muda de cor a cada
reinicio da API nao e identidade visual, e sim bug intermitente.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from typing import Final

from app.game import balance
from app.game.aleatoriedade import GeradorAleatorio
from app.game.erros import AvatarInvalido

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
