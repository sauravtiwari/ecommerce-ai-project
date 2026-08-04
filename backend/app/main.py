"""FastAPI application entrypoint.

Run with:  uvicorn app.main:app --reload
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
from app.routers import products

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Close pooled connections on shutdown instead of leaving them to time out."""
    yield
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

# Adds Access-Control-Allow-Origin so browsers permit cross-origin reads.
# Not a security control: non-browser clients ignore CORS entirely.
app.add_middleware(
    CORSMiddleware,
    # Never "*" here -- the wildcard is incompatible with allow_credentials.
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # needed once auth cookies exist
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    environment: str
    database: str
    database_time: str | None = None


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> HealthResponse:
    """Health check that queries the database.

    A hardcoded {"status": "ok"} would stay green through an outage, so this
    runs a real query. Render gates deploys on this endpoint.
    """
    try:
        result = await session.execute(text("SELECT now()"))
        return HealthResponse(
            status="ok",
            environment=settings.environment,
            database="connected",
            database_time=result.scalar_one().isoformat(),
        )
    except Exception as exc:  # noqa: BLE001 - any failure means degraded
        # 200 with "degraded" beats a stack trace for a diagnostic endpoint.
        # Never include str(exc): it can contain the connection string.
        return HealthResponse(
            status="degraded",
            environment=settings.environment,
            database=f"unavailable ({type(exc).__name__})",
        )


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """Liveness only -- answers "is the process up?" without touching Postgres."""
    return {"service": settings.app_name, "docs": "/docs"}
