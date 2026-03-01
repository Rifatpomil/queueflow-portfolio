"""Service model – a category of service offered at a location."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.location import Location
    from app.models.ticket import Ticket


class Service(Base):
    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    # If None → service is available at all locations in the tenant
    location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # One-letter prefix used for ticket numbers (e.g. "G" → G-0001)
    prefix: Mapped[str] = mapped_column(String(10), default="G")
    category: Mapped[str | None] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(default=True)
    avg_service_minutes: Mapped[int] = mapped_column(default=5)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    tenant: Mapped[Tenant] = relationship()
    location: Mapped[Location | None] = relationship(back_populates="services")
    tickets: Mapped[list[Ticket]] = relationship(back_populates="service")

    __table_args__ = (
        Index("ix_services_tenant_id", "tenant_id"),
        Index("ix_services_location_id", "location_id"),
    )

    def __repr__(self) -> str:
        return f"<Service id={self.id} name={self.name!r}>"
