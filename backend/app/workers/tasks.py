"""Celery background tasks."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task
from sqlalchemy import create_engine, delete, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Engine created once when the worker process starts — never per-task call.
# This keeps a small connection pool (default pool_size=5) that all tasks in
# this worker process share, instead of opening a new connection on every task.
_sync_engine = create_engine(
    settings.database_sync_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
_SyncSessionFactory = sessionmaker(bind=_sync_engine)


def _get_sync_session() -> Session:
    """Return a synchronous SQLAlchemy session from the shared pool."""
    return _SyncSessionFactory()


@shared_task(
    name="app.workers.tasks.kpi_rollup",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def kpi_rollup(self) -> dict:
    """
    Hourly KPI rollup – aggregate wait/service times for the past hour.

    Design note: the live analytics API (GET /v1/analytics/…) queries the
    ``tickets`` table on demand, so this task does **not** write to a separate
    ``kpi_aggregates`` table. Instead it emits structured log lines that are
    consumed by the Prometheus log-scraper or a log aggregation pipeline.

    If query latency becomes a concern at scale, promote this task to write
    into a ``kpi_aggregates`` table and update the analytics API to read from
    there instead of scanning ``tickets`` directly.
    """
    try:
        with _get_sync_session() as session:
            now = datetime.now(tz=timezone.utc)
            hour_ago = now - timedelta(hours=1)

            result = session.execute(
                text("""
                SELECT
                    l.id as location_id,
                    l.name as location_name,
                    COUNT(*) FILTER (WHERE t.status = 'COMPLETED') as completed,
                    COUNT(*) FILTER (WHERE t.status = 'WAITING') as waiting,
                    AVG(EXTRACT(EPOCH FROM (t.called_at - t.created_at)))
                        FILTER (WHERE t.called_at IS NOT NULL) as avg_wait_secs,
                    AVG(EXTRACT(EPOCH FROM (t.completed_at - t.service_started_at)))
                        FILTER (WHERE t.completed_at IS NOT NULL
                                  AND t.service_started_at IS NOT NULL) as avg_service_secs
                FROM tickets t
                JOIN locations l ON l.id = t.location_id
                WHERE t.created_at >= :from_dt AND t.created_at < :to_dt
                GROUP BY l.id, l.name
                """),
                {"from_dt": hour_ago, "to_dt": now},
            )
            rows = result.fetchall()
            for row in rows:
                logger.info(
                    "kpi_rollup location=%s completed=%s waiting=%s "
                    "avg_wait=%.1f avg_service=%.1f",
                    row.location_name,
                    row.completed,
                    row.waiting,
                    row.avg_wait_secs or 0,
                    row.avg_service_secs or 0,
                )
            return {"locations_processed": len(rows), "period_start": hour_ago.isoformat()}
    except Exception as exc:
        logger.error("kpi_rollup_failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task(
    name="app.workers.tasks.cleanup_idempotency_keys",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def cleanup_idempotency_keys(self) -> dict:
    """Delete expired idempotency keys."""
    try:
        with _get_sync_session() as session:
            from app.models.idempotency_key import IdempotencyKey

            result = session.execute(
                delete(IdempotencyKey).where(
                    IdempotencyKey.expires_at < datetime.now(tz=timezone.utc)
                )
            )
            session.commit()
            deleted = result.rowcount
            logger.info("cleanup_idempotency_keys deleted=%d", deleted)
            return {"deleted": deleted}
    except Exception as exc:
        raise self.retry(exc=exc)


@shared_task(
    name="app.workers.tasks.auto_no_show_called_tickets",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def auto_no_show_called_tickets(self) -> dict:
    """
    Auto-transition tickets stuck in CALLED state for > 5 minutes to NO_SHOW.
    This handles the case where a customer was called but never arrived.
    """
    try:
        with _get_sync_session() as session:
            from app.models.ticket import Ticket, TicketStatus
            from app.models.ticket_event import EventType, TicketEvent

            cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=5)

            stuck = session.execute(
                select(Ticket).where(
                    Ticket.status == TicketStatus.CALLED,
                    Ticket.called_at < cutoff,
                )
            ).scalars().all()

            for ticket in stuck:
                ticket.status = TicketStatus.NO_SHOW
                ticket.completed_at = datetime.now(tz=timezone.utc)
                event = TicketEvent(
                    ticket_id=ticket.id,
                    event_type=EventType.NO_SHOW,
                    payload_json={"reason": "auto_no_show"},
                )
                session.add(event)

            session.commit()
            logger.info("auto_no_show updated=%d", len(stuck))
            return {"updated": len(stuck)}
    except Exception as exc:
        raise self.retry(exc=exc)
