"""Counter / service station model."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.location import Location
    from app.models.interaction import Interaction


class Counter(Base):
    __tablename__ = "counters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    counter_type: Mapped[str] = mapped_column(String(50), default="standard")
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    location: Mapped[Location] = relationship(back_populates="counters")
    interactions: Mapped[list[Interaction]] = relationship(back_populates="counter")

    __table_args__ = (Index("ix_counters_location_id", "location_id"),)

    def __repr__(self) -> str:
        return f"<Counter id={self.id} name={self.name!r}>"
