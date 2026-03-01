"""Location model – a physical site within a tenant."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.counter import Counter
    from app.models.ticket import Ticket
    from app.models.service import Service


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="locations")
    counters: Mapped[list[Counter]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )
    tickets: Mapped[list[Ticket]] = relationship(back_populates="location")
    services: Mapped[list[Service]] = relationship(
        back_populates="location",
        primaryjoin="and_(Location.id==Service.location_id)",
    )

    __table_args__ = (Index("ix_locations_tenant_id", "tenant_id"),)

    def __repr__(self) -> str:
        return f"<Location id={self.id} name={self.name!r}>"
