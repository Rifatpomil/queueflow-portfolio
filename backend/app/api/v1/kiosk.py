"""Kiosk endpoints – public self-service ticket creation."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.api.deps import get_db, get_redis
from app.core.rate_limit import limiter
from app.models.location import Location
from app.repositories.ticket_repo import TicketRepository
from app.models.ticket import TicketStatus
from app.models.ticket_event import EventType, TicketEvent
from app.schemas.ticket import TicketRead

router = APIRouter(prefix="/kiosk", tags=["kiosk"])


class KioskTicketCreate(BaseModel):
    location_id: UUID
    service_id: UUID | None = None


@router.post(
    "/tickets",
    response_model=TicketRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create ticket from Kiosk (public)",
)
@limiter.limit("30/minute")
async def kiosk_create_ticket(
    request: Request,
    body: KioskTicketCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
) -> TicketRead:
    """Public ticket creation for Kiosk – tenant resolved from location."""
    result = await db.execute(select(Location).where(Location.id == body.location_id))
    loc = result.scalar_one_or_none()
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    repo = TicketRepository(db)
    tenant_id = loc.tenant_id

    if idempotency_key:
        existing = await repo.get_idempotency_key(tenant_id, idempotency_key)
        if existing and existing.resource_id:
            ticket = await repo.get(existing.resource_id)
            if ticket:
                return TicketRead.model_validate(ticket)

    number = await repo.next_number(body.location_id)
    ticket = await repo.create(
        tenant_id=tenant_id,
        location_id=body.location_id,
        service_id=body.service_id,
        channel_id=None,
        number=number,
        status=TicketStatus.WAITING,
        priority=5,
        notes=None,
    )

    event = TicketEvent(
        ticket_id=ticket.id,
        event_type=EventType.CREATED,
        from_status=None,
        actor_user_id=None,
    )
    db.add(event)
    await db.commit()
    await db.refresh(ticket)

    if idempotency_key:
        await repo.save_idempotency_key(
            tenant_id=tenant_id,
            key=idempotency_key,
            request_body={"location_id": str(body.location_id), "service_id": str(body.service_id) if body.service_id else None},
            resource_id=ticket.id,
            response_json={"id": str(ticket.id), "number": ticket.number},
        )
        await db.commit()

    try:
        await redis.publish(f"signage:{body.location_id}", "update")
    except Exception:
        pass

    return TicketRead.model_validate(ticket)
