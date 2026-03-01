"""Immutable event log – every ticket state transition is recorded here."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class EventType:
    CREATED = "CREATED"
    WAITING = "WAITING"
    CALLED = "CALLED"
    IN_SERVICE = "IN_SERVICE"
    HOLD = "HOLD"
    TRANSFERRED = "TRANSFERRED"
    COMPLETED = "COMPLETED"
    CANCELED = "CANCELED"
    NO_SHOW = "NO_SHOW"
    NOTE_ADDED = "NOTE_ADDED"


class TicketEvent(Base):
    """Append-only event log. Never update or delete rows."""

    __tablename__ = "ticket_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Explicit previous state makes audit queries trivial without replaying the log
    from_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    ticket: Mapped[Ticket] = relationship(back_populates="events")

    __table_args__ = (
        # Hot path: load all events for a given ticket in chronological order
        Index("ix_ticket_events_ticket_occurred", "ticket_id", "occurred_at"),
    )

    def __repr__(self) -> str:
        return f"<TicketEvent ticket={self.ticket_id} type={self.event_type!r}>"
