"""Shared Pydantic base models and response wrappers."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class APIModel(BaseModel):
    """Base for all API schemas – forbids extra fields, reads from ORM."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")


class PaginatedResponse(APIModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class ErrorDetail(APIModel):
    code: str
    message: str
    detail: Any | None = None


class HealthResponse(APIModel):
    status: str
    version: str
    timestamp: datetime
