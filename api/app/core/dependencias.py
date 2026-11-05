"""Dependencias compartilhadas pelas rotas protegidas (spec 002, tarefa 8).

`professor_atual` resolve professor e laboratorio de uma unica vez a partir do
token de portador, e e a unica porta de entrada da sessao: toda rota que
precisa saber "de quem e esse laboratorio" declara esta dependencia, em vez de
reimplementar a leitura do header em cada router.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.erros import NaoAutenticado
from app.core.seguranca import validar_token
from app.models import Laboratorio, Professor
from app.repositories import laboratorios as laboratorios_repo
from app.repositories import professores as professores_repo

# auto_error=False: queremos levantar o nosso NaoAutenticado, com o envelope
# padrao, em vez do 403 generico que o HTTPBearer devolveria sozinho quando o
# header esta ausente.
_portador = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class SessaoProfessor:
    """O professor autenticado e o laboratorio da sessao, resolvidos juntos."""

    professor: Professor
    laboratorio: Laboratorio


def professor_atual(
    credenciais: HTTPAuthorizationCredentials | None = Depends(_portador),
    sessao: Session = Depends(get_db),
) -> SessaoProfessor:
    """Levanta `NaoAutenticado` (401) sem token, com token invalido ou expirado.

    Um laboratorio ausente para um professor valido e inconsistencia de
    estado, nao falta de sessao: todo professor nasce com laboratorio na mesma
    transacao do registro (spec 002, regra 7), entao isso nunca deveria
    acontecer fora de um bug de dado.
    """
    if credenciais is None:
        raise NaoAutenticado()

    professor_id = validar_token(credenciais.credentials)
    professor = professores_repo.buscar_por_id(sessao, professor_id)
    if professor is None:
        raise NaoAutenticado()

    laboratorio = laboratorios_repo.buscar_por_professor_id(sessao, professor.id)
    if laboratorio is None:
        raise RuntimeError(f"Professor {professor.id} nao tem laboratorio associado.")

    return SessaoProfessor(professor=professor, laboratorio=laboratorio)
