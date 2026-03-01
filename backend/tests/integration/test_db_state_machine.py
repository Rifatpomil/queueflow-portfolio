"""
Integration test: DB-level state machine enforcement.

Verifies that the trigger rejects illegal ticket status transitions.
Requires PostgreSQL (trigger uses PL/pgSQL).
"""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket, TicketStatus
from app.models.ticket_event import TicketEvent
from tests.conftest import COUNTER_ID, LOCATION_ID, SERVICE_ID, TENANT_ID


@pytest.mark.asyncio
class TestDBStateMachine:
    """Trigger rejects illegal transitions."""

    @pytest.fixture(autouse=True)
    async def _skip_sqlite(self, db_session: AsyncSession):
        if "sqlite" in str(db_session.bind):
            pytest.skip("SQLite does not support PostgreSQL triggers")

    async def test_trigger_rejects_waiting_to_completed(
        self, db_session: AsyncSession, seeded_db
    ):
        """WAITING -> COMPLETED is illegal."""
        ticket = await self._create_ticket(db_session, TicketStatus.WAITING)
        with pytest.raises(Exception) as exc_info:
            await db_session.execute(
                text("UPDATE tickets SET status = 'COMPLETED' WHERE id = :id"),
                {"id": str(ticket.id)},
            )
            await db_session.commit()
        err = str(exc_info.value).lower()
        assert "invalid transition" in err or "invalid" in err
        await db_session.rollback()

    async def test_trigger_rejects_called_to_completed(
        self, db_session: AsyncSession, seeded_db
    ):
        """CALLED -> COMPLETED is illegal (must go through IN_SERVICE)."""
        ticket = await self._create_ticket(db_session, TicketStatus.CALLED)
        with pytest.raises(Exception) as exc_info:
            await db_session.execute(
                text("UPDATE tickets SET status = 'COMPLETED' WHERE id = :id"),
                {"id": str(ticket.id)},
            )
            await db_session.commit()
        err = str(exc_info.value).lower()
        assert "invalid transition" in err or "invalid" in err
        await db_session.rollback()

    async def test_trigger_allows_waiting_to_called(
        self, db_session: AsyncSession, seeded_db
    ):
        """WAITING -> CALLED is legal."""
        ticket = await self._create_ticket(db_session, TicketStatus.WAITING)
        await db_session.execute(
            text("UPDATE tickets SET status = 'CALLED', called_at = now() WHERE id = :id"),
            {"id": ticket.id},
        )
        await db_session.commit()
        await db_session.refresh(ticket)
        assert ticket.status == TicketStatus.CALLED

    async def test_trigger_rejects_terminal_transition(
        self, db_session: AsyncSession, seeded_db
    ):
        """COMPLETED cannot transition to any other state."""
        ticket = await self._create_ticket(db_session, TicketStatus.COMPLETED)
        with pytest.raises(Exception) as exc_info:
            await db_session.execute(
                text("UPDATE tickets SET status = 'WAITING' WHERE id = :id"),
                {"id": str(ticket.id)},
            )
            await db_session.commit()
        err = str(exc_info.value).lower()
        assert "terminal" in err
        await db_session.rollback()

    async def _create_ticket(self, session: AsyncSession, status: str) -> Ticket:
        import uuid

        ticket = Ticket(
            id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            location_id=LOCATION_ID,
            service_id=SERVICE_ID,
            number=1,
            status=status,
            priority=5,
        )
        session.add(ticket)
        await session.flush()
        return ticket


@pytest.mark.asyncio
class TestEventLogImmutability:
    """ticket_events is append-only: no UPDATE or DELETE."""

    @pytest.fixture(autouse=True)
    async def _skip_sqlite(self, db_session: AsyncSession):
        if "sqlite" in str(db_session.bind):
            pytest.skip("SQLite does not support PostgreSQL triggers")

    async def test_trigger_rejects_update_on_ticket_events(
        self, db_session: AsyncSession, seeded_db
    ):
        """UPDATE on ticket_events raises."""
        import uuid

        from app.models.ticket import Ticket, TicketStatus

        ticket = Ticket(
            id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            location_id=LOCATION_ID,
            service_id=SERVICE_ID,
            number=99,
            status=TicketStatus.WAITING,
            priority=5,
        )
        db_session.add(ticket)
        await db_session.flush()

        event = TicketEvent(
            id=uuid.uuid4(),
            ticket_id=ticket.id,
            event_type="CREATED",
            from_status=None,
        )
        db_session.add(event)
        await db_session.commit()

        with pytest.raises(Exception) as exc_info:
            await db_session.execute(
                text("UPDATE ticket_events SET event_type = 'WAITING' WHERE id = :id"),
                {"id": str(event.id)},
            )
            await db_session.commit()
        err = str(exc_info.value).lower()
        assert "append-only" in err or "not allowed" in err
        await db_session.rollback()

    async def test_trigger_rejects_delete_on_ticket_events(
        self, db_session: AsyncSession, seeded_db
    ):
        """DELETE on ticket_events raises."""
        import uuid

        from app.models.ticket import Ticket, TicketStatus

        ticket = Ticket(
            id=uuid.uuid4(),
            tenant_id=TENANT_ID,
            location_id=LOCATION_ID,
            service_id=SERVICE_ID,
            number=98,
            status=TicketStatus.WAITING,
            priority=5,
        )
        db_session.add(ticket)
        await db_session.flush()

        event = TicketEvent(
            id=uuid.uuid4(),
            ticket_id=ticket.id,
            event_type="CREATED",
            from_status=None,
        )
        db_session.add(event)
        await db_session.commit()

        with pytest.raises(Exception) as exc_info:
            await db_session.execute(
                text("DELETE FROM ticket_events WHERE id = :id"),
                {"id": str(event.id)},
            )
            await db_session.commit()
        err = str(exc_info.value).lower()
        assert "append-only" in err or "not allowed" in err
        await db_session.rollback()
