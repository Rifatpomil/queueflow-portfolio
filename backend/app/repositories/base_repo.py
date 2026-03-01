"""Generic repository base with common CRUD operations."""
from __future__ import annotations

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Thin data-access layer. No business logic lives here."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id: UUID) -> ModelT | None:
        return await self.session.get(self.model, id)

    async def get_or_404(self, id: UUID) -> ModelT:
        from fastapi import HTTPException, status

        obj = await self.get(id)
        if obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{self.model.__name__} {id} not found",
            )
        return obj

    async def list(
        self,
        *filters: Any,
        limit: int = 100,
        offset: int = 0,
        order_by: Any = None,
    ) -> list[ModelT]:
        q = select(self.model).where(*filters).offset(offset).limit(limit)
        if order_by is not None:
            q = q.order_by(order_by)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def count(self, *filters: Any) -> int:
        from sqlalchemy import func, select

        q = select(func.count()).select_from(self.model).where(*filters)
        result = await self.session.execute(q)
        return result.scalar_one()

    async def create(self, **kwargs: Any) -> ModelT:
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: ModelT, **kwargs: Any) -> ModelT:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()
