"""Application settings, loaded from the environment.

No secrets live here -- this file declares which settings exist; values come
from `.env` locally and from real environment variables in production.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # tolerate unrelated vars already in the environment
    )

    app_name: str = "E-Commerce AI API"
    environment: str = "development"

    # No default: a missing DATABASE_URL must stop the app at startup rather
    # than let it connect somewhere unintended.
    database_url: str

    # NoDecode is required: pydantic-settings JSON-decodes complex types inside
    # the env source, before validators run, so a plain comma-separated string
    # would fail to parse.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",  # a different origin to a browser
    ]

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, v: str) -> str:
        """Convert a hosted provider's URL into one asyncpg accepts.

        Neon/Render/Supabase emit `postgresql://...?sslmode=require`. The async
        engine needs the `+asyncpg` driver, and asyncpg rejects libpq-only
        query params (TLS is applied in db.py instead).
        """
        for old in ("postgres://", "postgresql://"):
            if v.startswith(old):
                v = v.replace(old, "postgresql+asyncpg://", 1)
                break

        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection string")

        if "?" in v:
            base, _, query = v.partition("?")
            kept = [
                p
                for p in query.split("&")
                if p.split("=")[0] not in {"sslmode", "channel_binding", "options"}
            ]
            v = f"{base}?{'&'.join(kept)}" if kept else base

        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: str | list[str]) -> list[str]:
        """Accept `CORS_ORIGINS=https://a.com,https://b.com`."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def is_remote_database(self) -> bool:
        """Hosted databases need TLS; local Postgres does not offer it."""
        return not any(h in self.database_url for h in ("localhost", "127.0.0.1"))


@lru_cache
def get_settings() -> Settings:
    """Cached so the .env file is parsed once, not per request.

    Tests can call `get_settings.cache_clear()` to point at another database.
    """
    return Settings()
