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
