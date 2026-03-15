"""AI-powered endpoints – smart suggestions, predictions, insights."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.location import Location
from app.services.ai_service import AIService


router = APIRouter(prefix="/ai", tags=["ai"])


class SuggestServiceRequest(BaseModel):
    query: str
    location_id: UUID


class SuggestServiceResponse(BaseModel):
    suggested_service_id: str | None
    suggested_service_name: str | None
    confidence: float


@router.post(
    "/suggest-service",
    response_model=SuggestServiceResponse,
    summary="AI: Suggest service from natural language (auth required)",
)
async def suggest_service(
    body: SuggestServiceRequest,
    db: AsyncSession = Depends(get_db),
    actor=Depends(get_current_user),
) -> SuggestServiceResponse:
    """Describe what you need; AI suggests the best service."""
    svc = AIService(db)
    result = await svc.suggest_service(
        tenant_id=UUID(actor.tenant_id),
        location_id=body.location_id,
        query=body.query,
    )
    return SuggestServiceResponse(**result)


@router.post(
    "/kiosk/suggest-service",
    response_model=SuggestServiceResponse,
    summary="AI: Suggest service (public, for Kiosk)",
)
async def kiosk_suggest_service(
    body: SuggestServiceRequest,
    db: AsyncSession = Depends(get_db),
) -> SuggestServiceResponse:
    """Public endpoint for Kiosk – looks up tenant from location."""
    result = await db.execute(select(Location).where(Location.id == body.location_id))
    loc = result.scalar_one_or_none()
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    svc = AIService(db)
    result_dict = await svc.suggest_service(
        tenant_id=loc.tenant_id,
        location_id=body.location_id,
        query=body.query,
    )
    return SuggestServiceResponse(**result_dict)


@router.get(
    "/predict-wait/{location_id}",
    summary="AI: Predicted wait time in minutes",
)
async def predict_wait(
    location_id: UUID,
    db: AsyncSession = Depends(get_db),
    actor=Depends(get_current_user),
):
    """Get AI-predicted wait time based on queue depth and history."""
    svc = AIService(db)
    return await svc.predict_wait_time(location_id)


@router.get(
    "/insights/{location_id}",
    summary="AI: KPI insights and recommendations",
)
async def get_insights(
    location_id: UUID,
    from_dt: datetime = Query(..., alias="from"),
    to_dt: datetime = Query(..., alias="to"),
    db: AsyncSession = Depends(get_db),
    actor=Depends(get_current_user),
):
    """Get AI-summarized insights from analytics data."""
    svc = AIService(db)
    return await svc.get_insights(location_id, from_dt, to_dt)
