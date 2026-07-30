"""Application configuration.

The rule: nothing secret is written in this file. This file describes WHICH
settings exist and what type each one is. The VALUES arrive from the
environment -- a local `.env` file while developing, real environment
variables set in the Render dashboard in production.

That separation is what lets the exact same code run on your laptop and on a
server without a single `if production:` branch.
"""

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Every configurable value the app has, in one place.

    Subclassing BaseSettings means pydantic will populate each field below by
    looking for a matching environment variable (case-insensitive), falling
    back to the `.env` file. `app_name` is filled from APP_NAME,
    `database_url` from DATABASE_URL, and so on.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Your shell has dozens of unrelated variables (PATH, TEMP...). Without
        # this, pydantic would reject them as unexpected input and refuse to
        # start.
        extra="ignore",
    )

    # --- Fields WITH a default are optional ---
    # A sensible default means you only override them when you actually need to.
    app_name: str = "E-Commerce AI API"
    environment: str = "development"

    # --- Fields WITHOUT a default are required ---
    # There is deliberately no default here. If DATABASE_URL is missing, the
    # app refuses to start with a clear error naming the variable. The
    # alternative -- defaulting to some localhost string -- risks a production
    # server quietly connecting to the wrong database, or worse, appearing to
    # work while pointed somewhere it should not be.
    database_url: str

    @field_validator("database_url")
    @classmethod
    def _normalise_database_url(cls, v: str) -> str:
        """Make any provider's Postgres URL usable by SQLAlchemy + asyncpg.

        Neon, Render, Supabase and Heroku all hand you a URL meant for the
        standard C client library:

            postgresql://user:pass@host/db?sslmode=require&channel_binding=require

        Two things about that string break this stack:

        1. The scheme has no driver. SQLAlchemy's async engine needs
           `postgresql+asyncpg://`, otherwise it loads the *synchronous*
           psycopg driver and fails with a confusing "greenlet" error that
           says nothing about the real cause. (Some providers still emit the
           ancient `postgres://` scheme, so that is handled too.)

        2. `sslmode` and `channel_binding` are libpq parameters. asyncpg does
           not understand them and raises `TypeError: connect() got an
           unexpected keyword argument 'sslmode'`. TLS is still used -- it is
           configured in db.py via connect_args instead.

        Doing this once, here, means you can paste a provider's URL verbatim
        and it simply works.
        """
        for old, new in (
            ("postgres://", "postgresql+asyncpg://"),
            ("postgresql://", "postgresql+asyncpg://"),
        ):
            if v.startswith(old):
                v = v.replace(old, new, 1)
                break

        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL connection string"
            )

        # Strip libpq-only query parameters that asyncpg rejects.
        if "?" in v:
            base, _, query = v.partition("?")
            kept = [
                part
                for part in query.split("&")
                if part.split("=")[0]
                not in {"sslmode", "channel_binding", "options"}
            ]
            v = f"{base}?{'&'.join(kept)}" if kept else base

        return v

    @property
    def is_remote_database(self) -> bool:
        """True when the database is not on this machine.

        Used by db.py to decide whether to require TLS. Local Postgres does not
        speak TLS by default; every hosted provider requires it.
        """
        return not any(
            host in self.database_url for host in ("localhost", "127.0.0.1")
        )

    # --- CORS ---
    # Which browser origins may read this API's responses.
    #
    # The local default covers both spellings of your own machine, because a
    # browser treats "localhost" and "127.0.0.1" as DIFFERENT origins even
    # though they resolve to the same place. In production this is overridden
    # with the real Vercel URL.
    # `NoDecode` is load-bearing. For any complex type (list, dict, set),
    # pydantic-settings tries to JSON-decode the environment value inside the
    # .env source -- which happens BEFORE field validators run. So
    # `CORS_ORIGINS=http://localhost:3000` blows up as invalid JSON and the
    # validator below never gets a chance. NoDecode turns that decoding off and
    # hands the raw string to our validator instead.
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: str | list[str]) -> list[str]:
        """Accept `CORS_ORIGINS=https://a.com,https://b.com` in the .env file.

        Without this, pydantic sees a `list[str]` field and tries to parse the
        environment value as JSON -- so anything but `["https://a.com"]` fails
        with a confusing decode error. Splitting on commas is friendlier to
        type into a Render dashboard field.
        """
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    """Return the settings, reading the environment only once.

    `Settings()` re-reads and re-parses the `.env` file every time it is
    called. Calling it per request would mean filesystem I/O on every request
    for values that never change.

    `@lru_cache` memoizes the result: the first call builds the object, every
    later call returns that same instance. It also gives tests an escape
    hatch -- `get_settings.cache_clear()` forces a reload, which is how you
    point the app at a test database later.
    """
    return Settings()
