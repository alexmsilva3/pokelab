"""Caso de uso de credenciais: registro atomico do laboratorio e login (spec 002).

Este modulo e quem le o relogio, gera o gerador de aleatoriedade e abre a
transacao. `app.game.kit_inicial` recebe os dois ja prontos e so descreve o
que persistir; quem persiste e `app.repositories`.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import seguranca
from app.core.erros import CredenciaisInvalidas, KitJaConcedido, UsuarioEmUso
from app.game.kit_inicial import EspecieInicial, montar_kit_inicial
from app.models import Laboratorio, Professor
from app.repositories import especies as especies_repo
from app.repositories import kit_inicial as kit_repo
from app.repositories import laboratorios as laboratorios_repo
from app.repositories import professores as professores_repo

NOME_LABORATORIO_PADRAO = "Laboratorio Pokemon"

# Teto do inteiro de 64 bits com sinal: faixa da semente gravada na expedicao e
# usada tambem aqui, para que o kit seja reproduzivel como tudo mais (Artigo III).
SEMENTE_MAXIMA = 2**63 - 1

# Fragmentos que aparecem na mensagem do driver quando a constraint unica
# correspondente e violada. Nao ha API portavel para extrair "qual unique
# falhou" de um IntegrityError, entao a checagem e textual.
_FRAGMENTOS_USUARIO_EM_USO = ("usuario_normalizado", "laboratorios_professor_id")


@dataclass(frozen=True, slots=True)
class SessaoCriada:
    """O que registro e login devolvem: o token e o estado inicial do professor."""

    token: str
    professor: Professor
    laboratorio: Laboratorio


def registrar(
    sessao: Session,
    *,
    usuario: str,
    senha: str,
    nome_exibicao: str | None = None,
    nome_laboratorio: str | None = None,
) -> SessaoCriada:
    """Cria professor, laboratorio e o kit inicial numa unica transacao.

    As unique de `professores.usuario_normalizado` e `laboratorios.professor_id`
    sao a rede de seguranca contra dois registros concorrentes com o mesmo
    usuario (criterio de aceite 9 da spec 002): o perdedor da corrida recebe
    `IntegrityError` ao tentar gravar, que vira aqui o erro de dominio
    `UsuarioEmUso` em vez de vazar um 500. Como o professor e o laboratorio
    nascem juntos nesta mesma transacao, o kit nunca e concedido duas vezes
    para a mesma conta: ou a transacao inteira entra, ou nenhuma linha fica.
    """
    try:
        professor = professores_repo.criar(
            sessao,
            usuario=usuario,
            senha_hash=seguranca.hash_senha(senha),
            nome_exibicao=nome_exibicao or usuario,
        )
        laboratorio = laboratorios_repo.criar(
            sessao,
            professor_id=professor.id,
            nome=nome_laboratorio or NOME_LABORATORIO_PADRAO,
        )

        _conceder_kit(sessao, laboratorio)

        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        mensagem_original = str(erro.orig)
        if any(fragmento in mensagem_original for fragmento in _FRAGMENTOS_USUARIO_EM_USO):
            raise UsuarioEmUso() from erro
        raise

    return SessaoCriada(
        token=seguranca.emitir_token(professor.id), professor=professor, laboratorio=laboratorio
    )


def _conceder_kit(sessao: Session, laboratorio: Laboratorio) -> None:
    """Concede o kit inicial exatamente uma vez (invariante 10, Artigo VII).

    A linha do laboratorio e travada e `starters_concedidos` e relido dentro da
    transacao. A unique de `professor_id` ja barra dois registros concorrentes,
    mas nao barra uma segunda concessao sobre um laboratorio existente — e e
    justamente esse o caminho que duplicaria tres Pokemon e um treinador.
    """
    travado = laboratorios_repo.travar_para_concessao(sessao, laboratorio.id)
    if travado is None or travado.starters_concedidos:
        raise KitJaConcedido()

    especies = [
        EspecieInicial(
            id=especie.id, nome=especie.nome, curva_crescimento=especie.curva_crescimento
        )
        for especie in especies_repo.buscar_iniciais(sessao)
    ]

    # A semente fica gravada: o kit de qualquer laboratorio pode ser remontado
    # identico a partir dela, que e o que o Artigo III exige de toda rolagem.
    semente = random.randrange(SEMENTE_MAXIMA)
    kit = montar_kit_inicial(especies, random.Random(semente))

    kit_repo.persistir(sessao, travado.id, kit, agora=datetime.now(UTC))
    travado.semente_kit_inicial = semente
    laboratorios_repo.marcar_starters_concedidos(sessao, travado)


def autenticar(sessao: Session, *, usuario: str, senha: str) -> SessaoCriada:
    """Verifica usuario e senha; a mesma recusa para os dois casos (regra 10).

    `verificar_senha` roda sempre, mesmo quando o usuario nao existe, contra
    um hash descartavel — sem isso o tempo de resposta denunciaria quais
    contas existem.
    """
    professor = professores_repo.buscar_por_usuario(sessao, usuario)
    hash_para_comparar = professor.senha_hash if professor else seguranca.HASH_DESCARTAVEL
    senha_confere = seguranca.verificar_senha(senha, hash_para_comparar)

    if professor is None or not senha_confere:
        raise CredenciaisInvalidas()

    professores_repo.marcar_acesso(sessao, professor, datetime.now(UTC))
    laboratorio = laboratorios_repo.buscar_por_professor_id(sessao, professor.id)
    sessao.commit()

    return SessaoCriada(
        token=seguranca.emitir_token(professor.id), professor=professor, laboratorio=laboratorio
    )
