"""Analytics service – wraps analytics repository with validation."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TokenPayload
from app.models.location import Location
from app.repositories.analytics_repo import AnalyticsRepository
from app.schemas.analytics import KPISummary, TimeSeriesPoint, TimeSeriesResponse

VALID_METRICS = {"wait_time", "service_time", "queue_length", "throughput"}
VALID_INTERVALS = {"1 hour", "15 minutes", "1 day"}


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = AnalyticsRepository(session)

    async def _check_location_tenant(self, location_id: UUID, actor: TokenPayload) -> None:
        """Verify the location belongs to the requesting actor's tenant (prevents cross-tenant data leakage)."""
        result = await self.session.execute(
            select(Location).where(Location.id == location_id)
        )
        loc = result.scalar_one_or_none()
        if loc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
        if str(loc.tenant_id) != actor.tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

    async def get_summary(
        self,
        location_id: UUID,
        from_dt: datetime,
        to_dt: datetime,
        actor: TokenPayload,
    ) -> KPISummary:
        await self._check_location_tenant(location_id, actor)
        if from_dt >= to_dt:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="from must be before to",
            )
        data = await self.repo.kpi_summary(location_id, from_dt, to_dt)
        return KPISummary(
            location_id=location_id,
            from_dt=from_dt,
            to_dt=to_dt,
            **data,
        )

    async def get_timeseries(
        self,
        location_id: UUID,
        from_dt: datetime,
        to_dt: datetime,
        metric: str,
        interval: str,
        actor: TokenPayload,
    ) -> TimeSeriesResponse:
        await self._check_location_tenant(location_id, actor)
        if metric not in VALID_METRICS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"metric must be one of {VALID_METRICS}",
            )
        if interval not in VALID_INTERVALS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"interval must be one of {VALID_INTERVALS}",
            )
        rows = await self.repo.timeseries(location_id, from_dt, to_dt, metric, interval)
        return TimeSeriesResponse(
            location_id=location_id,
            metric=metric,
            interval=interval,
            data=[TimeSeriesPoint(bucket=r["bucket"], value=r["value"]) for r in rows],
        )
