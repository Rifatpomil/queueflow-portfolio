"""Interaction – a single service episode at a counter."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.ticket import Ticket
    from app.models.counter import Counter


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False
    )
    counter_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("counters.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # e.g. "completed", "transferred", "no_show"
    outcome: Mapped[str | None] = mapped_column(String(30))

    # Relationships
    ticket: Mapped[Ticket] = relationship(back_populates="interactions")
    counter: Mapped[Counter | None] = relationship(back_populates="interactions")

    __table_args__ = (
        # Needed for analytics queries: service time per counter over a date range
        Index("ix_interactions_counter_started", "counter_id", "started_at"),
        Index("ix_interactions_ticket_id", "ticket_id"),
    )

    def __repr__(self) -> str:
        return f"<Interaction id={self.id} ticket={self.ticket_id}>"
