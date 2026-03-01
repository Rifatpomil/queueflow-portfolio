"""Idempotency key store for safe request replay."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    # SHA-256 of the full request body to detect body mismatches
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # ID of the resource that was created (ticket, etc.)
    resource_id: Mapped[uuid.UUID | None] = mapped_column()
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # Primary lookup: (tenant, key) → must be unique and fast
        UniqueConstraint("tenant_id", "key", name="uq_idempotency_tenant_key"),
        Index("ix_idempotency_tenant_key", "tenant_id", "key"),
        Index("ix_idempotency_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<IdempotencyKey key={self.key!r} tenant={self.tenant_id}>"
