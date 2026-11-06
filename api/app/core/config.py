"""Configuracao da aplicacao, lida do ambiente.

Nada em app/game/ pode importar este modulo (Artigo I da constituicao).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Valor de exemplo que vem do .env.example e do default do campo abaixo. Uma
# producao rodando com esta chave assinaria token de sessao com um segredo que
# qualquer um le no repositorio publico.
SECRET_KEY_DESENVOLVIMENTO = "desenvolvimento-apenas"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    postgres_user: str = "pokelab"
    postgres_password: str = "pokelab"
    postgres_db: str = "pokelab"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    secret_key: str = SECRET_KEY_DESENVOLVIMENTO
    access_token_expire_minutes: int = 1440

    # ADR-004: multiplica a duracao de toda expedicao. 1.0 = tempo real,
    # 0.01 = vinte minutos viram doze segundos.
    expedition_time_scale: float = 1.0

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


# Qualquer valor que esteja escrito em algum arquivo do repositorio e, por
# definicao, publico. Comparar so com o default do campo deixava passar a chave
# do .env.example, que e justamente a que um deploy feito por `make setup` usa.
SECRET_KEYS_PUBLICAS = frozenset(
    {
        SECRET_KEY_DESENVOLVIMENTO,
        "trocar-em-producao",
        "trocar-em-producao-chave-longa-e-aleatoria",
        "changeme",
        "secret",
    }
)

TAMANHO_MINIMO_SECRET_KEY = 32


def validar_producao(settings: Settings) -> None:
    """Recusa subir em producao com um segredo fraco ou conhecido.

    Um JWT assinado com um segredo que esta no repositorio e um JWT que qualquer
    um forja: basta ler o .env.example e montar um token com o `sub` de outro
    professor. Isto nao e um aviso de lint, e motivo para o processo nao iniciar.
    """
    if settings.environment != "production":
        return

    chave = settings.secret_key.strip()

    if chave in SECRET_KEYS_PUBLICAS:
        raise RuntimeError(
            "SECRET_KEY e um valor publicado no repositorio e nao serve em producao. "
            "Gere uma chave propria, por exemplo com `python -c "
            '"import secrets; print(secrets.token_urlsafe(48))"`.'
        )

    if len(chave) < TAMANHO_MINIMO_SECRET_KEY:
        raise RuntimeError(
            f"SECRET_KEY tem {len(chave)} caracteres; o minimo em producao e "
            f"{TAMANHO_MINIMO_SECRET_KEY}."
        )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    validar_producao(settings)
    return settings
