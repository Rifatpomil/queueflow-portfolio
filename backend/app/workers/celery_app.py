"""Celery application factory."""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "queueflow",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Periodic tasks
    beat_schedule={
        "kpi-rollup-hourly": {
            "task": "app.workers.tasks.kpi_rollup",
            "schedule": crontab(minute=5),  # Run 5 minutes past every hour
            "options": {"queue": "analytics"},
        },
        "cleanup-expired-idempotency-keys": {
            "task": "app.workers.tasks.cleanup_idempotency_keys",
            "schedule": crontab(hour=2, minute=0),  # Daily at 02:00 UTC
            "options": {"queue": "default"},
        },
        "auto-no-show": {
            "task": "app.workers.tasks.auto_no_show_called_tickets",
            "schedule": crontab(minute="*/10"),  # Every 10 minutes
            "options": {"queue": "default"},
        },
    },
)
