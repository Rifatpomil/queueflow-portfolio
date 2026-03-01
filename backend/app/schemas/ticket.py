"""Pydantic schemas for tickets."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common import APIModel
from app.models.ticket import TicketStatus


class TicketCreate(APIModel):
    location_id: UUID
    service_id: UUID | None = None
    channel_id: UUID | None = None
    priority: int = Field(default=5, ge=1, le=10)
    notes: str | None = None


class TicketTransfer(APIModel):
    target_service_id: UUID
    target_location_id: UUID | None = None
    notes: str | None = None


class TicketRead(APIModel):
    id: UUID
    tenant_id: UUID
    location_id: UUID
    service_id: UUID | None
    channel_id: UUID | None
    assigned_counter_id: UUID | None
    number: int
    display_number: str
    status: str
    priority: int
    notes: str | None
    created_at: datetime
    updated_at: datetime
    called_at: datetime | None
    service_started_at: datetime | None
    completed_at: datetime | None


class TicketEventRead(APIModel):
    id: UUID
    ticket_id: UUID
    event_type: str
    actor_user_id: UUID | None
    payload_json: dict | None
    occurred_at: datetime


class TicketWithEvents(TicketRead):
    events: list[TicketEventRead] = []
