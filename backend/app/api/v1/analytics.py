"""Analytics endpoints."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.security import TokenPayload
from app.schemas.analytics import KPISummary, TimeSeriesResponse
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "/location/{location_id}/summary",
    response_model=KPISummary,
    summary="KPI summary for a location over a date range",
)
async def get_summary(
    location_id: UUID,
    from_dt: datetime = Query(..., alias="from"),
    to_dt: datetime = Query(..., alias="to"),
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> KPISummary:
    svc = AnalyticsService(db)
    return await svc.get_summary(location_id, from_dt, to_dt, actor)


@router.get(
    "/location/{location_id}/timeseries",
    response_model=TimeSeriesResponse,
    summary="Time-series metric for a location",
)
async def get_timeseries(
    location_id: UUID,
    metric: str = Query(..., description="wait_time | service_time | queue_length | throughput"),
    interval: str = Query(default="1 hour", description="1 hour | 15 minutes | 1 day"),
    from_dt: datetime = Query(..., alias="from"),
    to_dt: datetime = Query(..., alias="to"),
    db: AsyncSession = Depends(get_db),
    actor: TokenPayload = Depends(get_current_user),
) -> TimeSeriesResponse:
    svc = AnalyticsService(db)
    return await svc.get_timeseries(location_id, from_dt, to_dt, metric, interval, actor)
