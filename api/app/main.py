from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.erros import ErroDeAplicacao
from app.game.erros import ErroDeDominio
from app.routers import auth, health, me

settings = get_settings()

app = FastAPI(
    title="PokeLab API",
    description="Laboratorio Pokemon: treinadores, expedicoes e relatorios de campo.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ErroDeAplicacao)
async def tratar_erro_de_aplicacao(request: Request, exc: ErroDeAplicacao) -> JSONResponse:
    """Traduz erro de autenticacao, conflito ou escopo para o envelope padrao."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "erro": {"codigo": exc.codigo, "mensagem": exc.mensagem, "detalhes": exc.detalhes}
        },
    )


# Campos cujo valor nunca pode voltar numa resposta, nem dentro de um erro de
# validacao (regra 4 e criterio 11 da spec 002).
CAMPOS_SENSIVEIS = frozenset({"senha", "senha_hash", "password", "token"})


def _sanitizar_erro_de_validacao(erro: dict) -> dict:
    """Remove o valor rejeitado do relato de erro do Pydantic.

    O 422 padrao do FastAPI ecoa em `input` exatamente o que o cliente mandou.
    Quando o campo rejeitado e a senha, a senha em texto claro volta no corpo e
    dali para log de proxy, APM e devtools. O valor nao acrescenta nada a quem
    digitou: a pessoa sabe o que escreveu.
    """
    local = [str(parte) for parte in erro.get("loc", ())]
    limpo = {
        "campo": ".".join(local[1:]) or ".".join(local),
        "tipo": erro.get("type"),
        "mensagem": erro.get("msg"),
    }
    contexto = erro.get("ctx")
    if contexto and not (set(local) & CAMPOS_SENSIVEIS):
        limpo["contexto"] = {
            chave: valor
            for chave, valor in contexto.items()
            if isinstance(valor, (str, int, float, bool))
        }
    return limpo


@app.exception_handler(RequestValidationError)
async def tratar_erro_de_validacao(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Poe o 422 do Pydantic dentro do envelope da aplicacao, sem o valor enviado."""
    return JSONResponse(
        status_code=422,
        content={
            "erro": {
                "codigo": "ENTRADA_INVALIDA",
                "mensagem": "Os dados enviados nao sao validos. Confira os campos indicados.",
                "detalhes": {
                    "campos": [_sanitizar_erro_de_validacao(erro) for erro in exc.errors()]
                },
            }
        },
    )


@app.exception_handler(ErroDeDominio)
async def tratar_erro_de_dominio(request: Request, exc: ErroDeDominio) -> JSONResponse:
    """Uma regra de `app.game` foi violada sem que o servico a traduzisse antes.

    Isso so acontece por inconsistencia de dados (ex.: seed incompleto), nunca
    por entrada de um professor legitimo — por isso vira 500, nao 4xx.
    """
    return JSONResponse(
        status_code=500,
        content={
            "erro": {
                "codigo": "ERRO_INTERNO_DE_DOMINIO",
                "mensagem": str(exc),
                "detalhes": None,
            }
        },
    )


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(me.router)
