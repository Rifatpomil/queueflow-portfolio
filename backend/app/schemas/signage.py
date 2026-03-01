"""Schemas for the public signage view."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.schemas.common import APIModel


class SignageTicketEntry(APIModel):
    id: UUID
    display_number: str
    status: str
    counter_name: str | None
    service_name: str | None
    called_at: datetime | None


class SignageSnapshot(APIModel):
    location_id: UUID
    location_name: str
    now_serving: list[SignageTicketEntry]     # IN_SERVICE tickets
    recently_called: list[SignageTicketEntry]  # CALLED tickets (last 10)
    waiting_count: int
    avg_wait_minutes: float | None
    snapshot_at: datetime
