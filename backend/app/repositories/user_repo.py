"""User repository."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.user import User, UserRole
from app.repositories.base_repo import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
            .where(User.tenant_id == tenant_id, User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_with_roles(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User)
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_roles(self, user_id: UUID) -> list[str]:
        user = await self.get_with_roles(user_id)
        if not user:
            return []
        return [ur.role.name for ur in user.user_roles]
