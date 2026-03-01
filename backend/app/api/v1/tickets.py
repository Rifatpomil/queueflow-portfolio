"""Ticket lifecycle endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

import redis.asyncio as aioredis

from app.api.deps import get_current_user, get_db, get_redis
from app.core.rate_limit import limiter
from app.core.security import TokenPayload
from app.models.ticket import TicketStatus
from app.repositories.ticket_repo import TicketRepository
from app.schemas.common import PaginatedResponse
from app.schemas.ticket import TicketCreate, TicketRead, TicketTransfer, TicketWithEvents
from app.services.ticket_service import TicketService

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.post(
    "",
    response_model=TicketRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new ticket",
)
@limiter.limit("60/minute")
async def create_ticket(
    request: Request,
    body: TicketCreate,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> TicketRead:
    svc = TicketService(db, redis)
    ticket = await svc.create_ticket(body, actor, idempotency_key)
    return TicketRead.model_validate(ticket)


@router.get(
    "",
    response_model=list[TicketRead],
    summary="List tickets for a location",
)
async def list_tickets(
    location_id: UUID = Query(...),
    service_id: UUID | None = Query(default=None),
    ticket_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> list[TicketRead]:
    repo = TicketRepository(db)
    tickets = await repo.list_by_location(
        location_id, status=ticket_status, service_id=service_id, limit=limit, offset=offset
    )
    return [TicketRead.model_validate(t) for t in tickets]


@router.get("/{ticket_id}", response_model=TicketWithEvents)
async def get_ticket(
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> TicketWithEvents:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.ticket import Ticket
    from app.models.ticket_event import TicketEvent

    result = await db.execute(
        select(Ticket)
        .options(selectinload(Ticket.events))
        .where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if ticket is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Ticket not found")
    return TicketWithEvents.model_validate(ticket)


@router.post("/{ticket_id}/hold", response_model=TicketRead)
@limiter.limit("60/minute")
async def hold_ticket(
    request: Request,
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> TicketRead:
    svc = TicketService(db, redis)
    ticket = await svc.hold_ticket(ticket_id, actor)
    return TicketRead.model_validate(ticket)


@router.post("/{ticket_id}/cancel", response_model=TicketRead)
@limiter.limit("60/minute")
async def cancel_ticket(
    request: Request,
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> TicketRead:
    svc = TicketService(db, redis)
    ticket = await svc.cancel_ticket(ticket_id, actor)
    return TicketRead.model_validate(ticket)


@router.post("/{ticket_id}/no-show", response_model=TicketRead)
@limiter.limit("60/minute")
async def no_show(
    request: Request,
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> TicketRead:
    svc = TicketService(db, redis)
    ticket = await svc.no_show(ticket_id, actor)
    return TicketRead.model_validate(ticket)


@router.post("/{ticket_id}/start-service", response_model=TicketRead)
@limiter.limit("120/minute")
async def start_service(
    request: Request,
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TicketRead:
    svc = TicketService(db, redis)
    ticket = await svc.start_service(ticket_id, actor, idempotency_key)
    return TicketRead.model_validate(ticket)


@router.post("/{ticket_id}/complete", response_model=TicketRead)
@limiter.limit("120/minute")
async def complete_ticket(
    request: Request,
    ticket_id: UUID,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TicketRead:
    svc = TicketService(db, redis)
    ticket = await svc.complete_ticket(ticket_id, actor, idempotency_key)
    return TicketRead.model_validate(ticket)


@router.post("/{ticket_id}/transfer", response_model=TicketRead)
@limiter.limit("60/minute")
async def transfer_ticket(
    request: Request,
    ticket_id: UUID,
    body: TicketTransfer,
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
    redis: aioredis.Redis = Depends(get_redis),
) -> TicketRead:
    svc = TicketService(db, redis)
    ticket = await svc.transfer_ticket(ticket_id, body, actor)
    return TicketRead.model_validate(ticket)
