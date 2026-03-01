"""Async SQLAlchemy engine + session factory."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_pre_ping=True,
    echo=settings.is_dev,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency – yields a database session per request.

    When RLS_ENABLED=true, sets app.tenant_id and app.signage_location_id
    from request.state for Postgres Row-Level Security.
    """
    async with AsyncSessionLocal() as session:
        if settings.rls_enabled:
            tenant_id = getattr(request.state, "tenant_id", None)
            signage_location_id = getattr(request.state, "signage_location_id", None)
            if tenant_id:
                await session.execute(
                    text("SET LOCAL app.tenant_id = :tid"),
                    {"tid": str(tenant_id)},
                )
            if signage_location_id:
                await session.execute(
                    text("SET LOCAL app.signage_location_id = :lid"),
                    {"lid": str(signage_location_id)},
                )
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
