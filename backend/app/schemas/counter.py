from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import Field
from app.schemas.common import APIModel


class CounterCreate(APIModel):
    location_id: UUID
    name: str = Field(min_length=1, max_length=100)
    counter_type: str = "standard"


class CounterUpdate(APIModel):
    name: str | None = None
    counter_type: str | None = None
    active: bool | None = None


class CounterRead(APIModel):
    id: UUID
    location_id: UUID
    name: str
    counter_type: str
    active: bool
    created_at: datetime
