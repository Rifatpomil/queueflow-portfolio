"""Analytics repository – KPI queries."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Integer, Numeric, cast, func, literal_column, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket, TicketStatus


class AnalyticsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def kpi_summary(
        self, location_id: UUID, from_dt: datetime, to_dt: datetime
    ) -> dict:
        base_filter = [
            Ticket.location_id == location_id,
            Ticket.created_at >= from_dt,
            Ticket.created_at < to_dt,
        ]

        # Total counts by status
        counts_q = select(
            func.count().label("total"),
            func.count()
            .filter(Ticket.status == TicketStatus.COMPLETED)
            .label("completed"),
            func.count()
            .filter(Ticket.status == TicketStatus.CANCELED)
            .label("canceled"),
            func.count()
            .filter(Ticket.status == TicketStatus.NO_SHOW)
            .label("no_show"),
        ).where(*base_filter)

        # Avg + p95 wait time (created → called), in seconds
        wait_q = select(
            func.avg(
                func.extract("epoch", Ticket.called_at)
                - func.extract("epoch", Ticket.created_at)
            ).label("avg_wait"),
            func.percentile_cont(0.95)
            .within_group(
                (
                    func.extract("epoch", Ticket.called_at)
                    - func.extract("epoch", Ticket.created_at)
                ).asc()
            )
            .label("p95_wait"),
        ).where(*base_filter, Ticket.called_at.isnot(None))

        # Avg service time (service_started → completed), in seconds
        service_q = select(
            func.avg(
                func.extract("epoch", Ticket.completed_at)
                - func.extract("epoch", Ticket.service_started_at)
            ).label("avg_service")
        ).where(
            *base_filter,
            Ticket.completed_at.isnot(None),
            Ticket.service_started_at.isnot(None),
        )

        counts_res = (await self.session.execute(counts_q)).one()
        wait_res = (await self.session.execute(wait_q)).one()
        svc_res = (await self.session.execute(service_q)).one()

        duration_hours = max((to_dt - from_dt).total_seconds() / 3600, 1)
        throughput = counts_res.completed / duration_hours

        return {
            "total_tickets": counts_res.total,
            "completed_tickets": counts_res.completed,
            "canceled_tickets": counts_res.canceled,
            "no_show_tickets": counts_res.no_show,
            "avg_wait_seconds": float(wait_res.avg_wait) if wait_res.avg_wait else None,
            "p95_wait_seconds": float(wait_res.p95_wait) if wait_res.p95_wait else None,
            "avg_service_seconds": float(svc_res.avg_service) if svc_res.avg_service else None,
            "throughput_per_hour": round(throughput, 2),
        }

    async def timeseries(
        self,
        location_id: UUID,
        from_dt: datetime,
        to_dt: datetime,
        metric: str,
        interval: str = "1 hour",
    ) -> list[dict]:
        """
        Return time-bucketed data.
        metric: "wait_time" | "service_time" | "queue_length" | "throughput"
        interval: postgres interval string, e.g. "1 hour", "15 minutes"
        """
        bucket_expr = func.date_trunc(
            interval.split()[1] if len(interval.split()) > 1 else interval,
            Ticket.created_at,
        ).label("bucket")

        if metric == "wait_time":
            value_expr = func.avg(
                func.extract("epoch", Ticket.called_at)
                - func.extract("epoch", Ticket.created_at)
            ).label("value")
            extra_filter = [Ticket.called_at.isnot(None)]
        elif metric == "service_time":
            value_expr = func.avg(
                func.extract("epoch", Ticket.completed_at)
                - func.extract("epoch", Ticket.service_started_at)
            ).label("value")
            extra_filter = [
                Ticket.completed_at.isnot(None),
                Ticket.service_started_at.isnot(None),
            ]
        elif metric == "throughput":
            value_expr = func.count().label("value")
            extra_filter = [Ticket.status == TicketStatus.COMPLETED]
        else:  # queue_length – count of tickets created per bucket
            value_expr = func.count().label("value")
            extra_filter = []

        q = (
            select(bucket_expr, value_expr)
            .where(
                Ticket.location_id == location_id,
                Ticket.created_at >= from_dt,
                Ticket.created_at < to_dt,
                *extra_filter,
            )
            .group_by(literal_column("bucket"))
            .order_by(literal_column("bucket"))
        )
        result = await self.session.execute(q)
        return [{"bucket": row.bucket, "value": float(row.value or 0)} for row in result]
