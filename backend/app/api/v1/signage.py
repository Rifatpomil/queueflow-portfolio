"""Signage endpoints – snapshot + SSE stream."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.location import Location
from app.schemas.signage import SignageSnapshot
from app.services.signage_service import SignageService

router = APIRouter(prefix="/signage", tags=["signage"])


async def _get_location(location_id: UUID, db: AsyncSession) -> Location:
    result = await db.execute(select(Location).where(Location.id == location_id))
    loc = result.scalar_one_or_none()
    if loc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return loc


@router.get(
    "/{location_id}",
    response_model=SignageSnapshot,
    summary="Get a point-in-time signage snapshot (no auth required)",
)
@router.get(
    "/{location_id}/snapshot",
    response_model=SignageSnapshot,
    summary="Alias for GET /{location_id} – snapshot of called/in_service tickets",
)
async def get_signage_snapshot(
    location_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SignageSnapshot:
    """Public endpoint – no authentication required for signage displays."""
    loc = await _get_location(location_id, db)
    svc = SignageService(db)
    return await svc.get_snapshot(location_id, loc.name)


@router.get(
    "/{location_id}/stream",
    summary="Server-Sent Events stream of signage updates (no auth required)",
    response_class=StreamingResponse,
)
async def signage_stream(
    location_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """
    SSE stream – clients connect once and receive live signage updates.
    Each event is a JSON-encoded SignageSnapshot with id for reconnect.
    Heartbeat every 15s. Last-Event-ID header supported for reconnect.
    """
    loc = await _get_location(location_id, db)
    svc = SignageService(db)

    return StreamingResponse(
        svc.sse_stream(location_id, loc.name, last_event_id=last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
