"""Shared pytest fixtures for QueueFlow tests."""
from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set test environment BEFORE any app imports
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUTH_MODE", "dev")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("RLS_ENABLED", "false")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-tests-only")

# Use environment-provided DATABASE_URL or fall back to in-memory SQLite for unit tests
TEST_DB_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///:memory:",
)

from unittest.mock import AsyncMock

from app.core.config import get_settings
get_settings.cache_clear()

from app.db.base import Base
from app.db.session import get_db
from app.api.deps import get_redis
from app.main import app

# ── Database fixtures ─────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        # For Postgres: use Alembic. For SQLite (unit tests): create tables directly.
        if "sqlite" in TEST_DB_URL:
            # SQLite doesn't support JSONB → swap to JSON via monkey-patch
            from sqlalchemy.dialects.postgresql import JSONB
            from sqlalchemy import JSON
            import sqlalchemy.dialects.postgresql as pg_dialect
            pg_dialect.JSONB = JSON  # type: ignore

            await conn.run_sync(Base.metadata.create_all)
        else:
            # Postgres: tables created by Alembic migration in CI
            pass

    yield engine

    async with engine.begin() as conn:
        if "sqlite" in TEST_DB_URL:
            await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


# ── HTTP client fixture ───────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    # Provide a no-op Redis mock so tests don't need a running Redis instance.
    # Signage publishes are silently swallowed; SSE tests can override this fixture.
    mock_redis = AsyncMock()
    mock_redis.publish = AsyncMock(return_value=1)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: mock_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_pooled(db_session: AsyncSession, seeded_db) -> AsyncGenerator[AsyncClient, None]:
    """
    Client that uses real get_db (no override) so each request gets its own session.
    Use for concurrency tests where multiple requests must run in parallel with
    separate DB connections. Requires Postgres (skipped on SQLite).
    """
    if "sqlite" in str(db_session.bind):
        pytest.skip("client_pooled requires Postgres for real connection pool")

    mock_redis = AsyncMock()
    mock_redis.publish = AsyncMock(return_value=1)
    app.dependency_overrides[get_redis] = lambda: mock_redis
    # Do NOT override get_db – each request gets its own session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Auth helper ───────────────────────────────────────────────────────────────
@pytest.fixture
def admin_headers() -> dict[str, str]:
    from app.core.security import create_dev_token
    token = create_dev_token("admin@queueflow.dev")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def staff_headers() -> dict[str, str]:
    from app.core.security import create_dev_token
    token = create_dev_token("staff@queueflow.dev")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_headers() -> dict[str, str]:
    from app.core.security import create_dev_token
    token = create_dev_token("viewer@queueflow.dev")
    return {"Authorization": f"Bearer {token}"}


# ── Seed helpers ──────────────────────────────────────────────────────────────
TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
LOCATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000020")
SERVICE_ID = uuid.UUID("00000000-0000-0000-0000-000000000031")
COUNTER_ID = uuid.UUID("00000000-0000-0000-0000-000000000041")


STAFF_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
ROLE_STAFF_ID = uuid.UUID("00000000-0000-0000-0000-000000000063")


@pytest_asyncio.fixture
async def seeded_db(db_session: AsyncSession):
    """Insert minimal data needed for integration tests."""
    from app.models.tenant import Tenant
    from app.models.location import Location
    from app.models.service import Service
    from app.models.counter import Counter
    from app.models.user import User, Role, UserRole
    from app.core.security import hash_password

    tenant = Tenant(id=TENANT_ID, name="Test Tenant", slug="test-tenant")
    location = Location(
        id=LOCATION_ID, tenant_id=TENANT_ID, name="Test Location", timezone="UTC"
    )
    service = Service(
        id=SERVICE_ID, tenant_id=TENANT_ID, location_id=LOCATION_ID,
        name="General", prefix="G",
    )
    counter = Counter(id=COUNTER_ID, location_id=LOCATION_ID, name="Counter 1")
    role = Role(id=ROLE_STAFF_ID, tenant_id=TENANT_ID, name="staff", description="Staff")
    user = User(
        id=STAFF_USER_ID,
        tenant_id=TENANT_ID,
        email="staff@queueflow.dev",
        display_name="Staff",
        hashed_password=hash_password("test"),
    )

    db_session.add_all([tenant, location, service, counter, role, user])
    await db_session.flush()
    db_session.add(UserRole(user_id=STAFF_USER_ID, role_id=ROLE_STAFF_ID))
    await db_session.commit()

    yield {"tenant": tenant, "location": location, "service": service, "counter": counter}
