from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import EmailStr, Field
from app.schemas.common import APIModel


class UserCreate(APIModel):
    tenant_id: UUID
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=255)
    password: str | None = None  # None for SSO-only users


class UserUpdate(APIModel):
    display_name: str | None = None
    status: str | None = None


class RoleRead(APIModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str | None


class UserRead(APIModel):
    id: UUID
    tenant_id: UUID
    email: str
    display_name: str
    status: str
    created_at: datetime
    roles: list[str] = []


class RoleAssignment(APIModel):
    role_id: UUID
    location_id: UUID | None = None


class DevLoginRequest(APIModel):
    email: EmailStr


class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
