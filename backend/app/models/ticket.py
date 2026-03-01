"""Ticket model – core entity representing one customer in the queue."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.location import Location
    from app.models.service import Service
    from app.models.channel import Channel
    from app.models.counter import Counter
    from app.models.ticket_event import TicketEvent
    from app.models.interaction import Interaction


# Ticket status values – kept as plain strings (not enums) for DB portability
class TicketStatus:
    CREATED = "CREATED"
    WAITING = "WAITING"
    CALLED = "CALLED"
    IN_SERVICE = "IN_SERVICE"
    HOLD = "HOLD"
    TRANSFERRED = "TRANSFERRED"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    NO_SHOW = "NO_SHOW"

    TERMINAL = {COMPLETED, CANCELED, NO_SHOW}
    ALL = {CREATED, WAITING, CALLED, IN_SERVICE, HOLD, TRANSFERRED, COMPLETED, CANCELED, NO_SHOW}


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id"), nullable=False
    )
    service_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("services.id"), nullable=True
    )
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("channels.id"), nullable=True
    )
    assigned_counter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("counters.id"), nullable=True
    )
    # Display-friendly number per location, e.g. 42 → "G-0042"
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TicketStatus.WAITING)
    # 1 = highest priority, 10 = lowest
    priority: Mapped[int] = mapped_column(Integer, default=5)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    service_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    tenant: Mapped[Tenant] = relationship(back_populates="tickets")
    location: Mapped[Location] = relationship(back_populates="tickets")
    service: Mapped[Service | None] = relationship(back_populates="tickets")
    channel: Mapped[Channel | None] = relationship()
    assigned_counter: Mapped[Counter | None] = relationship(
        foreign_keys=[assigned_counter_id]
    )
    events: Mapped[list[TicketEvent]] = relationship(
        back_populates="ticket",
        order_by="TicketEvent.occurred_at",
        cascade="all, delete-orphan",
    )
    interactions: Mapped[list[Interaction]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan"
    )

    __table_args__ = (
        # Used by call-next query and queue list queries
        Index("ix_tickets_location_status_created", "location_id", "status", "created_at"),
        # Used by service-filtered queue queries
        Index("ix_tickets_service_status_created", "service_id", "status", "created_at"),
        Index("ix_tickets_tenant_id", "tenant_id"),
        # Used to display the formatted ticket number (number lookup per location)
        Index("ix_tickets_number_location", "number", "location_id"),
    )

    @property
    def display_number(self) -> str:
        """Human-readable ticket number, e.g. 'G-0042'.

        Uses ``__dict__`` to avoid triggering a lazy-load in async sessions —
        only uses the service prefix if the relationship is already loaded.
        """
        prefix = "T"
        service = self.__dict__.get("service")
        if service is not None:
            prefix = getattr(service, "prefix", None) or "T"
        return f"{prefix}-{self.number:04d}"

    def __repr__(self) -> str:
        return f"<Ticket id={self.id} number={self.number} status={self.status!r}>"
