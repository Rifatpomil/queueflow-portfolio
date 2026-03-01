"""Signage service – real-time display data for a location."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger
from app.repositories.ticket_repo import TicketRepository
from app.schemas.signage import SignageSnapshot, SignageTicketEntry
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


class SignageService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = TicketRepository(session)
        self.settings = get_settings()

    async def get_snapshot(self, location_id: UUID, location_name: str) -> SignageSnapshot:
        data = await self.repo.signage_snapshot(location_id)

        def _to_entry(t) -> SignageTicketEntry:
            return SignageTicketEntry(
                id=t.id,
                display_number=t.display_number,
                status=t.status,
                counter_name=t.assigned_counter.name if t.assigned_counter else None,
                service_name=t.service.name if t.service else None,
                called_at=t.called_at,
            )

        avg_secs = data["avg_wait_seconds"]
        return SignageSnapshot(
            location_id=location_id,
            location_name=location_name,
            now_serving=[_to_entry(t) for t in data["in_service"]],
            recently_called=[_to_entry(t) for t in data["recently_called"]],
            waiting_count=data["waiting_count"],
            avg_wait_minutes=round(avg_secs / 60, 1) if avg_secs else None,
            snapshot_at=datetime.now(tz=timezone.utc),
        )

    async def sse_stream(
        self,
        location_id: UUID,
        location_name: str,
        last_event_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Server-Sent Events generator.

        Sends an initial snapshot, then listens on the Redis pub/sub channel
        ``signage:{location_id}`` and re-sends the snapshot on every update.
        Heartbeat every 15s keeps connections alive through proxies.
        Each event includes an increasing id for Last-Event-ID reconnect handling.
        """
        channel = f"signage:{location_id}"
        r = aioredis.from_url(self.settings.redis_url)
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)

        HEARTBEAT_SECONDS = 15
        seq = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0

        def _event(sequence: int, data: str | None = None) -> str:
            lines = [f"id: {sequence}"]
            if data:
                lines.append(f"data: {data}")
            return "\n".join(lines) + "\n\n"

        try:
            # Send initial snapshot (or on reconnect, client gets fresh state)
            seq += 1
            snapshot = await self.get_snapshot(location_id, location_name)
            yield _event(seq, snapshot.model_dump_json())

            while True:
                try:
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=HEARTBEAT_SECONDS,
                    )
                except asyncio.TimeoutError:
                    message = None

                if message and message.get("type") == "message":
                    seq += 1
                    snapshot = await self.get_snapshot(location_id, location_name)
                    yield _event(seq, snapshot.model_dump_json())
                else:
                    seq += 1
                    # Heartbeat with id for reconnect continuity (comment line, no data)
                    yield f"id: {seq}\n: heartbeat\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
                await r.aclose()
            except Exception:
                pass
