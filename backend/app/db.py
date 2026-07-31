"""Database engine, connection pool, and per-request sessions.

    engine        -- owns the connection pool. One per process.
    SessionLocal  -- factory producing sessions. One per application.
    session       -- short-lived workspace. One per request.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

settings = get_settings()

# Opens no connections; the pool fills lazily on first use.
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.environment == "development",  # log generated SQL
    # Hosted providers drop idle connections silently, causing a random
    # failure on the first request after a quiet period.
    pool_pre_ping=True,
    # Re-applies the TLS requirement that config.py stripped from the URL.
    connect_args={"ssl": "require"} if settings.is_remote_database else {},
    # Free-tier databases cap connections well below the usual default.
    pool_size=5,
    max_overflow=5,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # Keeps attributes readable after commit(), avoiding an extra SELECT when
    # serializing a just-saved object to JSON.
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency supplying one session per request.

    `async with` guarantees the connection returns to the pool even if the
    endpoint raises -- otherwise a failing route leaks one per request.
    """
    async with SessionLocal() as session:
        yield session
