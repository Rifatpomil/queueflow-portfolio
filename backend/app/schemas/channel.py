from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import Field
from app.schemas.common import APIModel


class ChannelCreate(APIModel):
    tenant_id: UUID
    name: str = Field(min_length=1, max_length=100)


class ChannelUpdate(APIModel):
    name: str | None = None
    active: bool | None = None


class ChannelRead(APIModel):
    id: UUID
    tenant_id: UUID
    name: str
    active: bool
    created_at: datetime
