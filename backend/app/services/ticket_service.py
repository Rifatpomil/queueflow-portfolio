"""
Ticket business-logic service.

This layer owns all RBAC checks and business rules. Routers call
service methods; service methods call repositories.
"""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import TokenPayload
from app.models.audit_log import AuditLog
from app.models.interaction import Interaction
from app.models.ticket import Ticket, TicketStatus
from app.repositories.ticket_repo import TicketRepository
from app.schemas.ticket import TicketCreate, TicketTransfer
from app.state_machine.ticket_fsm import InvalidTransitionError

logger = get_logger(__name__)

# ── Role → permitted actions ──────────────────────────────────────────────────
WRITE_ROLES = {"admin", "manager", "staff"}
READ_ROLES = {"admin", "manager", "staff", "viewer"}


def _require_role(actor: TokenPayload, *roles: str) -> None:
    if not actor.has_role(*roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of roles: {list(roles)}",
        )


class TicketService:
    def __init__(self, session: AsyncSession, redis=None) -> None:
        self.session = session
        self.repo = TicketRepository(session)
        self._redis = redis

    async def create_ticket(
        self,
        data: TicketCreate,
        actor: TokenPayload,
        idempotency_key: str | None = None,
    ) -> Ticket:
        _require_role(actor, *WRITE_ROLES)

        # Idempotency check
        if idempotency_key:
            existing = await self.repo.get_idempotency_key(
                UUID(actor.tenant_id), idempotency_key
            )
            if existing and existing.resource_id:
                ticket = await self.repo.get(existing.resource_id)
                if ticket:
                    logger.info("idempotency_hit", key=idempotency_key)
                    return ticket

        number = await self.repo.next_number(data.location_id)
        ticket = await self.repo.create(
            tenant_id=UUID(actor.tenant_id),
            location_id=data.location_id,
            service_id=data.service_id,
            channel_id=data.channel_id,
            number=number,
            status=TicketStatus.WAITING,
            priority=data.priority,
            notes=data.notes,
        )

        # Record creation event
        from app.models.ticket_event import EventType, TicketEvent
        from datetime import datetime, timezone

        event = TicketEvent(
            ticket_id=ticket.id,
            event_type=EventType.CREATED,
            from_status=None,  # no previous state — this is the origin event
            actor_user_id=actor.user_id,
        )
        self.session.add(event)

        await self.session.commit()
        await self.session.refresh(ticket)

        # Persist idempotency record
        if idempotency_key:
            body_dict = json.loads(data.model_dump_json())
            await self.repo.save_idempotency_key(
                tenant_id=UUID(actor.tenant_id),
                key=idempotency_key,
                request_body=body_dict,
                resource_id=ticket.id,
                response_json={"id": str(ticket.id), "number": ticket.number},
            )
            await self.session.commit()

        logger.info("ticket_created", ticket_id=str(ticket.id), number=number)
        await self._publish_signage(ticket.location_id)
        return ticket

    async def hold_ticket(self, ticket_id: UUID, actor: TokenPayload) -> Ticket:
        _require_role(actor, *WRITE_ROLES)
        ticket = await self.repo.get_or_404(ticket_id)
        self._check_tenant(ticket, actor)
        try:
            ticket = await self.repo.transition_status(
                ticket, TicketStatus.HOLD, actor.user_id
            )
        except InvalidTransitionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        await self.session.commit()
        await self._publish_signage(ticket.location_id)
        return ticket

    async def cancel_ticket(
        self, ticket_id: UUID, actor: TokenPayload
    ) -> Ticket:
        _require_role(actor, *WRITE_ROLES)
        ticket = await self.repo.get_or_404(ticket_id)
        self._check_tenant(ticket, actor)
        try:
            ticket = await self.repo.transition_status(
                ticket, TicketStatus.CANCELED, actor.user_id
            )
        except InvalidTransitionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        await self.session.commit()
        await self._publish_signage(ticket.location_id)
        return ticket

    async def no_show(self, ticket_id: UUID, actor: TokenPayload) -> Ticket:
        _require_role(actor, *WRITE_ROLES)
        ticket = await self.repo.get_or_404(ticket_id)
        self._check_tenant(ticket, actor)
        try:
            ticket = await self.repo.transition_status(
                ticket, TicketStatus.NO_SHOW, actor.user_id
            )
        except InvalidTransitionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        await self.session.commit()
        await self._publish_signage(ticket.location_id)
        return ticket

    async def start_service(
        self,
        ticket_id: UUID,
        actor: TokenPayload,
        idempotency_key: str | None = None,
    ) -> Ticket:
        _require_role(actor, *WRITE_ROLES)
        if idempotency_key:
            existing = await self.repo.get_idempotency_key(
                UUID(actor.tenant_id), idempotency_key
            )
            if existing:
                body_hash = self.repo._hash_body({"ticket_id": str(ticket_id)})
                if existing.request_hash != body_hash:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Idempotency key reused with different request",
                    )
                if existing.resource_id:
                    ticket = await self.repo.get(existing.resource_id)
                    if ticket:
                        logger.info("idempotency_hit", key=idempotency_key)
                        return ticket

        ticket = await self.repo.get_or_404(ticket_id)
        self._check_tenant(ticket, actor)
        try:
            ticket = await self.repo.transition_status(
                ticket, TicketStatus.IN_SERVICE, actor.user_id
            )
        except InvalidTransitionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

        # Open an interaction record
        from datetime import datetime, timezone
        interaction = Interaction(
            ticket_id=ticket.id,
            counter_id=ticket.assigned_counter_id,
            started_at=datetime.now(tz=timezone.utc),
        )
        self.session.add(interaction)

        await self.session.commit()
        await self.session.refresh(ticket)

        if idempotency_key:
            body_dict = {"ticket_id": str(ticket_id)}
            await self.repo.save_idempotency_key(
                tenant_id=UUID(actor.tenant_id),
                key=idempotency_key,
                request_body=body_dict,
                resource_id=ticket.id,
                response_json=json.loads(
                    self._ticket_to_read(ticket).model_dump_json()
                ),
            )
            await self.session.commit()

        await self._publish_signage(ticket.location_id)
        return ticket

    async def complete_ticket(
        self,
        ticket_id: UUID,
        actor: TokenPayload,
        idempotency_key: str | None = None,
    ) -> Ticket:
        _require_role(actor, *WRITE_ROLES)
        if idempotency_key:
            existing = await self.repo.get_idempotency_key(
                UUID(actor.tenant_id), idempotency_key
            )
            if existing:
                body_hash = self.repo._hash_body({"ticket_id": str(ticket_id)})
                if existing.request_hash != body_hash:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Idempotency key reused with different request",
                    )
                if existing.resource_id:
                    ticket = await self.repo.get(existing.resource_id)
                    if ticket:
                        logger.info("idempotency_hit", key=idempotency_key)
                        return ticket

        ticket = await self.repo.get_or_404(ticket_id)
        self._check_tenant(ticket, actor)
        try:
            ticket = await self.repo.transition_status(
                ticket, TicketStatus.COMPLETED, actor.user_id
            )
        except InvalidTransitionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

        # Close the open interaction
        from datetime import datetime, timezone
        from sqlalchemy import update
        from app.models.interaction import Interaction

        await self.session.execute(
            update(Interaction)
            .where(Interaction.ticket_id == ticket.id, Interaction.ended_at.is_(None))
            .values(ended_at=datetime.now(tz=timezone.utc), outcome="completed")
        )
        await self.session.commit()
        await self.session.refresh(ticket)

        if idempotency_key:
            body_dict = {"ticket_id": str(ticket_id)}
            await self.repo.save_idempotency_key(
                tenant_id=UUID(actor.tenant_id),
                key=idempotency_key,
                request_body=body_dict,
                resource_id=ticket.id,
                response_json=json.loads(
                    self._ticket_to_read(ticket).model_dump_json()
                ),
            )
            await self.session.commit()

        await self._publish_signage(ticket.location_id)
        return ticket

    def _ticket_to_read(self, ticket: Ticket) -> "TicketRead":
        from app.schemas.ticket import TicketRead
        return TicketRead.model_validate(ticket)

    async def transfer_ticket(
        self, ticket_id: UUID, data: TicketTransfer, actor: TokenPayload
    ) -> Ticket:
        _require_role(actor, *WRITE_ROLES)
        ticket = await self.repo.get_or_404(ticket_id)
        self._check_tenant(ticket, actor)
        try:
            ticket = await self.repo.transition_status(
                ticket,
                TicketStatus.TRANSFERRED,
                actor.user_id,
                payload={
                    "target_service_id": str(data.target_service_id),
                    "target_location_id": str(data.target_location_id)
                    if data.target_location_id
                    else None,
                },
            )
        except InvalidTransitionError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

        # Re-queue at new service / location
        new_location = data.target_location_id or ticket.location_id
        ticket = await self.repo.update(
            ticket,
            service_id=data.target_service_id,
            location_id=new_location,
            assigned_counter_id=None,
            status=TicketStatus.WAITING,
        )

        from app.models.ticket_event import EventType, TicketEvent
        from datetime import datetime, timezone
        re_queue_event = TicketEvent(
            ticket_id=ticket.id,
            event_type=EventType.WAITING,
            actor_user_id=actor.user_id,
            occurred_at=datetime.now(tz=timezone.utc),
        )
        self.session.add(re_queue_event)
        await self.session.commit()
        await self._publish_signage(ticket.location_id)
        return ticket

    # ── RBAC / tenant helpers ──────────────────────────────────────────────────
    def _check_tenant(self, ticket: Ticket, actor: TokenPayload) -> None:
        if str(ticket.tenant_id) != actor.tenant_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant mismatch")

    # ── Signage pub/sub ────────────────────────────────────────────────────────
    async def _publish_signage(self, location_id: UUID) -> None:
        """Fire-and-forget Redis publish for SSE consumers.

        Uses the shared Redis client injected at construction time (app.state.redis).
        If no client was provided (e.g. in unit tests) the publish is silently skipped.
        """
        if self._redis is None:
            return
        try:
            await self._redis.publish(f"signage:{location_id}", "update")
        except Exception as exc:
            logger.warning("signage_publish_failed", error=str(exc))
