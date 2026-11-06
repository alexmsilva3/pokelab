#!/usr/bin/env bash
#
# Cria a conta de desenvolvimento descrita no .env, se ela ainda nao existir.
#
# Existe para que ninguem precise decorar nem colar senha em lugar nenhum: as
# credenciais vivem no .env, que nao e versionado, e este script so as consome.
#
# Idempotente: rodar de novo com a conta ja criada apenas confirma o acesso.

set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

if [ ! -f .env ]; then
  echo "crie o .env primeiro: cp .env.example .env" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
. ./.env
set +a

USUARIO="${DEV_PROFESSOR_USUARIO:-professor}"
SENHA="${DEV_PROFESSOR_SENHA:-}"
LABORATORIO="${DEV_PROFESSOR_LABORATORIO:-Lab Pallet}"
BASE="http://localhost:${API_PORT:-8000}"

if [ -z "$SENHA" ]; then
  echo "DEV_PROFESSOR_SENHA vazia no .env" >&2
  exit 1
fi

if ! curl -sf -m 5 "$BASE/health" >/dev/null; then
  echo "API fora do ar em $BASE. Rode 'make up' antes." >&2
  exit 1
fi

corpo() {
  python3 - "$USUARIO" "$SENHA" "$LABORATORIO" <<'PY'
import json, sys
print(json.dumps({
    "usuario": sys.argv[1],
    "senha": sys.argv[2],
    "nome_laboratorio": sys.argv[3],
}))
PY
}

resposta="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/auth/register" \
  -H 'Content-Type: application/json' -d "$(corpo)")"

case "$resposta" in
  201) echo "conta de desenvolvimento criada: $USUARIO" ;;
  409) echo "conta $USUARIO ja existia" ;;
  *)   echo "registro recusado (HTTP $resposta)" >&2; exit 1 ;;
esac

login="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$(python3 -c 'import json,sys; print(json.dumps({"usuario": sys.argv[1], "senha": sys.argv[2]}))' "$USUARIO" "$SENHA")")"

if [ "$login" = "200" ]; then
  echo "login confere. Entre em http://localhost:${WEB_PORT:-5173} com o usuario e a senha do seu .env"
else
  echo "a conta existe mas a senha do .env nao confere (HTTP $login)." >&2
  echo "Use outro DEV_PROFESSOR_USUARIO no .env, ou apague a conta antiga." >&2
  exit 1
fi
