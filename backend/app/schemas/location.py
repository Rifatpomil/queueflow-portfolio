from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import Field
from app.schemas.common import APIModel


class LocationCreate(APIModel):
    tenant_id: UUID
    name: str = Field(min_length=1, max_length=255)
    address: str | None = None
    timezone: str = "UTC"


class LocationUpdate(APIModel):
    name: str | None = None
    address: str | None = None
    timezone: str | None = None
    active: bool | None = None


class LocationRead(APIModel):
    id: UUID
    tenant_id: UUID
    name: str
    address: str | None
    timezone: str
    active: bool
    created_at: datetime
