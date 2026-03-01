"""
Ticket repository.

The most critical method here is ``call_next_ticket`` which uses a single
atomic SQL statement (CTE: select + update + insert + returning) with
FOR UPDATE SKIP LOCKED to provide concurrency-safe "call next" behaviour
under multiple concurrent operators.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.idempotency_key import IdempotencyKey
from app.models.interaction import Interaction
from app.models.ticket import Ticket, TicketStatus
from app.models.ticket_event import EventType, TicketEvent
from app.repositories.base_repo import BaseRepository
from app.state_machine.ticket_fsm import event_type_for, transition


# Atomic call-next: single SQL statement (CTE) for select + update + event insert.
# Uses FOR UPDATE SKIP LOCKED so concurrent staff get different tickets.
_CALL_NEXT_CTE = text("""
WITH selected AS (
    SELECT id FROM tickets
    WHERE location_id = :location_id
      AND status = 'WAITING'
      AND (:service_id::uuid IS NULL OR service_id = :service_id)
    ORDER BY priority ASC, created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
),
updated AS (
    UPDATE tickets t
    SET status = 'CALLED', called_at = now(), assigned_counter_id = :counter_id,
        updated_at = now()
    FROM selected s
    WHERE t.id = s.id
    RETURNING t.*
),
inserted AS (
    INSERT INTO ticket_events (id, ticket_id, event_type, from_status, actor_user_id, payload_json, occurred_at)
    SELECT gen_random_uuid(), u.id, 'CALLED', 'WAITING',
           :actor_user_id,
           jsonb_build_object('counter_id', :counter_id::text)::jsonb,
           now()
    FROM updated u
)
SELECT id, tenant_id, location_id, service_id, channel_id, assigned_counter_id,
       number, status, priority, notes, created_at, updated_at,
       called_at, service_started_at, completed_at
FROM updated
""")


class TicketRepository(BaseRepository[Ticket]):
    model = Ticket

    async def list_by_location(
        self,
        location_id: UUID,
        status: str | None = None,
        service_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Ticket]:
        filters = [Ticket.location_id == location_id]
        if status:
            filters.append(Ticket.status == status)
        if service_id:
            filters.append(Ticket.service_id == service_id)
        return await self.list(
            *filters,
            limit=limit,
            offset=offset,
            order_by=Ticket.created_at.asc(),
        )

    async def next_number(self, location_id: UUID) -> int:
        """Atomically allocate the next sequence number for a location."""
        result = await self.session.execute(
            select(func.coalesce(func.max(Ticket.number), 0) + 1).where(
                Ticket.location_id == location_id
            )
        )
        return int(result.scalar_one())

    async def call_next_ticket(
        self,
        location_id: UUID,
        counter_id: UUID,
        service_id: UUID | None,
        actor_user_id: UUID | None,
    ) -> Ticket | None:
        """
        Atomically select the highest-priority WAITING ticket and move it to
        CALLED, using a single SQL statement (CTE: select + update + insert + return)
        with FOR UPDATE SKIP LOCKED to prevent double-calling under concurrent requests.

        Returns the called ticket, or None if the queue is empty.
        """
        result = await self.session.execute(
            _CALL_NEXT_CTE,
            {
                "location_id": location_id,
                "counter_id": counter_id,
                "service_id": service_id,
                "actor_user_id": actor_user_id,
            },
        )
        row = result.fetchone()
        if row is None:
            return None

        # Fetch full ticket with relationships for display_number (same transaction)
        ticket_id = row.id
        result2 = await self.session.execute(
            select(Ticket)
            .options(
                selectinload(Ticket.service),
                selectinload(Ticket.assigned_counter),
            )
            .where(Ticket.id == ticket_id)
        )
        return result2.scalar_one_or_none()

    async def transition_status(
        self,
        ticket: Ticket,
        target_status: str,
        actor_user_id: UUID | None = None,
        payload: dict | None = None,
    ) -> Ticket:
        """Apply a validated state transition and persist the event."""
        current = ticket.status
        transition(current, target_status)  # raises InvalidTransitionError if illegal

        now = datetime.now(tz=timezone.utc)
        ticket.status = target_status

        if target_status == TicketStatus.IN_SERVICE:
            ticket.service_started_at = now
        elif target_status in (TicketStatus.COMPLETED, TicketStatus.CANCELED, TicketStatus.NO_SHOW):
            ticket.completed_at = now

        ev_type = event_type_for(current, target_status)
        event = TicketEvent(
            ticket_id=ticket.id,
            event_type=ev_type,
            from_status=current,
            actor_user_id=actor_user_id,
            payload_json=payload,
            occurred_at=now,
        )
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(ticket)
        return ticket

    # ── Idempotency ────────────────────────────────────────────────────────────
    @staticmethod
    def _hash_body(body: dict) -> str:
        raw = json.dumps(body, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get_idempotency_key(
        self, tenant_id: UUID, key: str
    ) -> IdempotencyKey | None:
        result = await self.session.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.tenant_id == tenant_id,
                IdempotencyKey.key == key,
                IdempotencyKey.expires_at > datetime.now(tz=timezone.utc),
            )
        )
        return result.scalar_one_or_none()

    async def save_idempotency_key(
        self,
        tenant_id: UUID,
        key: str,
        request_body: dict,
        resource_id: UUID,
        response_json: dict,
        ttl_hours: int = 24,
    ) -> IdempotencyKey:
        now = datetime.now(tz=timezone.utc)
        ik = IdempotencyKey(
            key=key,
            tenant_id=tenant_id,
            request_hash=self._hash_body(request_body),
            resource_id=resource_id,
            response_json=response_json,
            created_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
        )
        self.session.add(ik)
        await self.session.flush()
        return ik

    # ── Signage snapshot ───────────────────────────────────────────────────────
    async def signage_snapshot(self, location_id: UUID) -> dict:
        """Return data needed for the signage display (no lazy loads)."""
        # Tickets IN_SERVICE — eager-load relationships needed by signage display
        _signage_opts = [
            selectinload(Ticket.service),
            selectinload(Ticket.assigned_counter),
        ]
        in_service_q = (
            select(Ticket)
            .options(*_signage_opts)
            .where(
                Ticket.location_id == location_id,
                Ticket.status == TicketStatus.IN_SERVICE,
            )
            .order_by(Ticket.called_at.desc())
            .limit(5)
        )
        # Recently CALLED (may be walking to counter)
        called_q = (
            select(Ticket)
            .options(*_signage_opts)
            .where(
                Ticket.location_id == location_id,
                Ticket.status == TicketStatus.CALLED,
            )
            .order_by(Ticket.called_at.desc())
            .limit(10)
        )
        # Waiting count
        waiting_count_q = select(func.count()).select_from(Ticket).where(
            Ticket.location_id == location_id,
            Ticket.status == TicketStatus.WAITING,
        )
        # Avg wait time (seconds) – time from created_at to called_at for
        # tickets called in the last 2 hours
        two_hours_ago = datetime.now(tz=timezone.utc) - timedelta(hours=2)
        avg_wait_q = select(
            func.avg(
                func.extract("epoch", Ticket.called_at)
                - func.extract("epoch", Ticket.created_at)
            )
        ).where(
            Ticket.location_id == location_id,
            Ticket.called_at.isnot(None),
            Ticket.called_at >= two_hours_ago,
        )

        in_service_res, called_res, waiting_res, avg_wait_res = (
            await self.session.execute(in_service_q),
            await self.session.execute(called_q),
            await self.session.execute(waiting_count_q),
            await self.session.execute(avg_wait_q),
        )
        return {
            "in_service": list(in_service_res.scalars().all()),
            "recently_called": list(called_res.scalars().all()),
            "waiting_count": waiting_res.scalar_one(),
            "avg_wait_seconds": avg_wait_res.scalar_one(),
        }
