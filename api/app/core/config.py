"""Configuracao da aplicacao, lida do ambiente.

Nada em app/game/ pode importar este modulo (Artigo I da constituicao).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    postgres_user: str = "pokelab"
    postgres_password: str = "pokelab"
    postgres_db: str = "pokelab"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    secret_key: str = "desenvolvimento-apenas"
    access_token_expire_minutes: int = 1440

    # ADR-004: divide a duracao de toda expedicao. 1.0 = tempo real.
    expedition_time_scale: float = 1.0

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
