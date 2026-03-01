"""Pydantic schemas for analytics endpoints."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.schemas.common import APIModel


class KPISummary(APIModel):
    location_id: UUID
    from_dt: datetime
    to_dt: datetime
    total_tickets: int
    completed_tickets: int
    canceled_tickets: int
    no_show_tickets: int
    avg_wait_seconds: float | None
    p95_wait_seconds: float | None
    avg_service_seconds: float | None
    throughput_per_hour: float


class TimeSeriesPoint(APIModel):
    bucket: datetime
    value: float


class TimeSeriesResponse(APIModel):
    location_id: UUID
    metric: str
    interval: str
    data: list[TimeSeriesPoint]
