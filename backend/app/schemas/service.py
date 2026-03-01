from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import Field
from app.schemas.common import APIModel


class ServiceCreate(APIModel):
    tenant_id: UUID
    location_id: UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    prefix: str = Field(default="G", min_length=1, max_length=10)
    category: str | None = None
    avg_service_minutes: int = 5


class ServiceUpdate(APIModel):
    name: str | None = None
    prefix: str | None = None
    category: str | None = None
    avg_service_minutes: int | None = None
    active: bool | None = None


class ServiceRead(APIModel):
    id: UUID
    tenant_id: UUID
    location_id: UUID | None
    name: str
    prefix: str
    category: str | None
    active: bool
    avg_service_minutes: int
    created_at: datetime
