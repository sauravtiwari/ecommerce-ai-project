"""FastAPI application entrypoint.

Start it with:  uvicorn app.main:app --reload
                        ^^^^^^^^ ^^^
                        module   variable

Read that argument as "import `app.main`, then find the variable named `app`
inside it". Uvicorn does not look for a magic filename -- you are handing it a
Python object by path.
"""

from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import engine, get_session

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks.

    Everything before `yield` runs once when the server boots; everything after
    runs once as it shuts down. Disposing the engine closes pooled connections
    politely instead of abandoning them for Postgres to time out -- which
    matters on a small free-tier database with a low connection limit.
    """
    yield
    await engine.dispose()


# This object IS the application: a routing table plus configuration.
# Creating it starts no server and opens no port.
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)


# Middleware wraps every request and response. This one inspects the incoming
# `Origin` header and, if it is on the allow-list, adds the
# `Access-Control-Allow-Origin` header that tells the browser it may let
# JavaScript read the response.
#
# What this does NOT do: it does not stop anyone from calling your API. curl,
# Postman, and a Python script ignore CORS entirely and always could. CORS
# governs whether a *browser* lets JavaScript on some other origin read the
# reply. It is not authentication, and it is not a firewall.
app.add_middleware(
    CORSMiddleware,
    # Explicit list, never ["*"] on anything that will hold a session. The
    # wildcard is incompatible with allow_credentials=True by design -- "any
    # site may read authenticated responses" is precisely the attack the
    # same-origin policy exists to prevent.
    allow_origins=settings.cors_origins,
    # Required later, when the browser must send auth cookies to /orders.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    """The response schema, and the contract the frontend codes against.

    This replaces the vague `dict[str, str]`. A dict says "strings mapped to
    strings"; this says exactly which fields exist and what each one may
    contain. `Literal` goes further and restricts `status` to two specific
    values -- so a typo like "OK" is a validation error, not a subtly broken
    frontend condition.
    """

    status: Literal["ok", "degraded"]
    environment: str
    database: str
    database_time: str | None = None


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HealthResponse:
    """Liveness check that actually touches the database.

    A health check returning a hardcoded {"status": "ok"} is worse than none at
    all: it reports healthy while the database is unreachable, so your
    monitoring stays green through an outage. This one runs a real query, so a
    green response means the whole chain works.

    Note what this function does NOT do: create a session, close a session, or
    handle a connection pool. It declares a need via Depends() and FastAPI
    satisfies it. That inversion is the "injection" part.
    """
    try:
        result = await session.execute(text("SELECT now()"))
        db_time = result.scalar_one()
        return HealthResponse(
            status="ok",
            environment=settings.environment,
            database="connected",
            database_time=db_time.isoformat(),
        )
    except Exception as exc:  # noqa: BLE001 - any failure means degraded
        # Deliberately returns HTTP 200 with status "degraded" rather than
        # raising a 500. This endpoint is a diagnostic: a readable answer about
        # what is broken is more useful than a stack trace. The type name is
        # included, but never the exception text -- that can leak the
        # connection string, and therefore the password, to anyone who calls it.
        return HealthResponse(
            status="degraded",
            environment=settings.environment,
            database=f"unavailable ({type(exc).__name__})",
        )


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """A cheap endpoint that does not touch the database.

    Useful for answering "is the process alive?" separately from "can it reach
    Postgres?" -- two different questions with two different fixes.
    """
    return {"service": settings.app_name, "docs": "/docs"}
