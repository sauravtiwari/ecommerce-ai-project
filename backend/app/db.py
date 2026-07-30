"""Database engine, connection pool, and per-request sessions.

Three objects live here, and the distinction between them matters:

    engine        -- owns the connection pool. ONE per application process.
    SessionLocal  -- a factory that produces sessions. ONE per application.
    session       -- a short-lived workspace. ONE per request.
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

# Creating the engine opens NO connections. It builds a pool manager that will
# open them lazily, on first use. That is why this is safe at import time.
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    # Log every SQL statement SQLAlchemy generates. In Phase 2 you will be
    # writing an ORM query and wanting to see the SQL it actually produced --
    # this is how. Noisy on purpose in development, off in production.
    echo=settings.environment == "development",
    # Send a cheap "are you still there?" before handing out a pooled
    # connection. Hosted Postgres providers and load balancers silently drop
    # connections that have been idle for a few minutes; without this you get
    # a random failure on the first request after a quiet period, which is
    # maddening to reproduce because it only happens when nobody is looking.
    pool_pre_ping=True,
    # Hosted providers require TLS and will refuse a plaintext connection.
    # config.py stripped `sslmode=require` out of the URL because asyncpg does
    # not accept it as a query parameter -- this is where that requirement is
    # re-applied, in the form asyncpg does understand.
    #
    # Your local Postgres has no TLS configured, so asking for it there would
    # fail. Hence the conditional.
    connect_args={"ssl": "require"} if settings.is_remote_database else {},
    # Free tiers cap total connections hard (Neon's free plan is far lower
    # than a self-hosted server's default 100). A pool sized for a beefy
    # machine will exhaust that limit and start refusing connections, so keep
    # it small and let requests queue briefly instead.
    pool_size=5,
    max_overflow=5,
)

# A factory, not a session. Calling SessionLocal() produces a new session.
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # By default SQLAlchemy expires every object after commit(), so touching
    # any attribute afterwards triggers a fresh SELECT. In a web app you
    # usually commit and then immediately serialize the object to JSON -- which
    # would mean a surprise extra query per field. Turning expiry off avoids
    # that.
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that supplies one session per request.

    The `yield` makes this a dependency with cleanup, and the shape is
    deliberate:

        code before yield  -> runs before the endpoint (setup)
        the yielded value  -> injected into the endpoint as an argument
        code after yield   -> runs after the response (teardown)

    Here `async with` provides the teardown: the session closes and its
    connection returns to the pool even if the endpoint raises an exception.
    Without that guarantee, one failing endpoint would leak a connection per
    request until the pool was exhausted and the app hung.

    Phase 3 revisits this to add transaction handling; for now it only
    guarantees the connection always goes back.
    """
    async with SessionLocal() as session:
        yield session
