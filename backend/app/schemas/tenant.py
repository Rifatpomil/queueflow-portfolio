from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import Field
from app.schemas.common import APIModel


class TenantCreate(APIModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(min_length=2, max_length=100, pattern=r"^[a-z0-9-]+$")


class TenantUpdate(APIModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    active: bool | None = None


class TenantRead(APIModel):
    id: UUID
    name: str
    slug: str
    active: bool
    created_at: datetime
