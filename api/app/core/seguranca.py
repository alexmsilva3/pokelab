"""Hash de senha e emissao/validacao de token de sessao (spec 002, tarefa 5).

Bcrypt via passlib para a senha, JWT de portador via python-jose para a sessao.
Sem refresh token nem revogacao na v1: um token de validade curta com relogin
manual resolve o problema real sem a maquina de estados que o resto traria.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.erros import NaoAutenticado

ALGORITMO_TOKEN = "HS256"

_contexto_senha = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Um hash valido de uma senha que nenhum professor digita. `autenticar()` o usa
# quando o usuario nao existe, para que a verificacao de hash rode sempre —
# sem isso, pular a comparacao faria login com usuario inexistente responder
# mais rapido que senha errada, denunciando pelo tempo quais contas existem
# (regra 10 da spec 002).
HASH_DESCARTAVEL = _contexto_senha.hash("nenhum-professor-usa-esta-senha-como-senha")


def hash_senha(senha: str) -> str:
    """Deriva o hash bcrypt guardado em `professores.senha_hash`."""
    return _contexto_senha.hash(senha)


def verificar_senha(senha: str, hash_guardado: str) -> bool:
    """Compara a senha em texto com um hash. Nunca levanta por hash malformado."""
    try:
        return _contexto_senha.verify(senha, hash_guardado)
    except ValueError:
        return False


def emitir_token(professor_id: uuid.UUID) -> str:
    """Emite o JWT de sessao para o professor, valido por `access_token_expire_minutes`."""
    settings = get_settings()
    expira_em = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(professor_id), "exp": expira_em}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITMO_TOKEN)


def validar_token(token: str) -> uuid.UUID:
    """Devolve o id do professor dono do token, ou levanta `NaoAutenticado`.

    Token expirado, assinatura invalida, token malformado e `sub` ausente ou
    que nao e um UUID produzem exatamente a mesma excecao: quem chama uma rota
    protegida nao tem por que distinguir esses casos entre si.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITMO_TOKEN])
        return uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError, TypeError):
        raise NaoAutenticado() from None
