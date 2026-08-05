"""Shared test fixtures.

Tests run against the real dev database, but every test executes inside a
SAVEPOINT that is rolled back afterward. Already-committed data (your 50
seeded products) is visible for reads; anything a test writes is undone before
the next test runs -- no separate test database needed for this phase.
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import get_settings
from app.db import get_session
from app.main import app


@pytest_asyncio.fixture
async def db_session():
    # A dedicated engine per test, not the app's module-level `engine`.
    # asyncpg connections are bound to the event loop they were created in,
    # and pytest-asyncio gives each test function its own loop -- reusing one
    # global engine across tests means later tests inherit a pool tied to an
    # already-closed loop. Creating and disposing one here keeps everything
    # inside a single test's loop.
    test_engine = create_async_engine(get_settings().database_url)
    connection = await test_engine.connect()
    await connection.begin()
    # join_transaction_mode="create_savepoint": when app code calls
    # session.commit(), SQLAlchemy releases a SAVEPOINT instead of committing
    # the outer transaction -- so the endpoint's own commit() runs unmodified,
    # and everything still unwinds when we roll back below.
    # expire_on_commit=False must match SessionLocal in app/db.py. With the
    # default (True), every attribute is expired after commit(), so reading
    # product.id in create_product's re-select triggers a lazy refresh -- IO
    # in the wrong place, raising MissingGreenlet. A test session that differs
    # from the real one produces failures the app does not actually have.
    session = AsyncSession(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    try:
        yield session
    finally:
        await session.close()
        await connection.rollback()
        await connection.close()
        await test_engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def _override_get_session():
        yield db_session

    # Swaps the real database dependency for the test session, without
    # touching a single line of the endpoint code.
    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
