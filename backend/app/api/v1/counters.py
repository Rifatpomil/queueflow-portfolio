"""Counter (call-next) endpoints."""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import redis.asyncio as aioredis

from app.api.deps import get_db, get_redis, require_staff
from app.core.rate_limit import limiter
from app.core.security import TokenPayload
from app.models.ticket import Ticket
from app.repositories.ticket_repo import TicketRepository
from app.schemas.ticket import TicketRead

router = APIRouter(prefix="/counters", tags=["counters"])

from pydantic import BaseModel


class CallNextBody(BaseModel):
    service_id: UUID | None = None


@router.post(
    "/{counter_id}/call-next",
    response_model=TicketRead | None,
    summary="Atomically call the next WAITING ticket for this counter",
)
@limiter.limit("120/minute")  # 2/sec per IP for operator workflows
async def call_next(
    request: Request,
    counter_id: UUID,
    body: CallNextBody = CallNextBody(),
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(require_staff),
    redis: aioredis.Redis = Depends(get_redis),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TicketRead | None:
    """
    Atomic call-next using single SQL CTE (FOR UPDATE SKIP LOCKED).
    Idempotency-Key header supported for safe retries.
    Returns 200 with the ticket, or 200 with null if the queue is empty.
    """
    from sqlalchemy import select

    from sqlalchemy.orm import selectinload

    from app.models.counter import Counter

    result = await db.execute(
        select(Counter)
        .options(selectinload(Counter.location))
        .where(Counter.id == counter_id)
    )
    counter = result.scalar_one_or_none()
    if counter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Counter not found")
    if str(counter.location.tenant_id) != actor.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

    repo = TicketRepository(db)
    tenant_id = UUID(actor.tenant_id)

    # Idempotency: return cached response if same key was used before
    if idempotency_key:
        existing = await repo.get_idempotency_key(tenant_id, idempotency_key)
        if existing and existing.resource_id:
            body_hash = repo._hash_body(body.model_dump(mode="json"))
            if existing.request_hash == body_hash:
                ticket = await db.execute(
                    select(Ticket)
                    .options(
                        selectinload(Ticket.service),
                        selectinload(Ticket.assigned_counter),
                    )
                    .where(Ticket.id == existing.resource_id)
                )
                t = ticket.scalar_one_or_none()
                if t:
                    return TicketRead.model_validate(t)
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency key reused with different request body",
                )

    ticket = await repo.call_next_ticket(
        location_id=counter.location_id,
        counter_id=counter_id,
        service_id=body.service_id,
        actor_user_id=actor.user_id,
    )
    await db.commit()

    if ticket is None:
        return None

    # Persist idempotency record when we successfully called a ticket
    if idempotency_key:
        body_dict = body.model_dump(mode="json")
        await repo.save_idempotency_key(
            tenant_id=tenant_id,
            key=idempotency_key,
            request_body=body_dict,
            resource_id=ticket.id,
            response_json=json.loads(TicketRead.model_validate(ticket).model_dump_json()),
        )
        await db.commit()

    from app.services.ticket_service import TicketService

    svc = TicketService(db, redis)
    await svc._publish_signage(ticket.location_id)

    return TicketRead.model_validate(ticket)
