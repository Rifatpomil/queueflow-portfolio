"""Tenant model – top-level isolation boundary."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.user import User
    from app.models.ticket import Ticket


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    locations: Mapped[list[Location]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    users: Mapped[list[User]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    tickets: Mapped[list[Ticket]] = relationship(back_populates="tenant")

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} name={self.name!r}>"
