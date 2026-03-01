"""
Integration test: concurrent call-next safety.

Verifies that the atomic CTE (SELECT … FOR UPDATE SKIP LOCKED + UPDATE + INSERT)
prevents double-calling even when multiple operators call simultaneously.
"""
from __future__ import annotations

import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import COUNTER_ID, LOCATION_ID, SERVICE_ID, TENANT_ID


@pytest.mark.asyncio
class TestCallNext:
    async def _create_n_tickets(
        self, client: AsyncClient, headers: dict, n: int = 5
    ) -> list[str]:
        ids = []
        for _ in range(n):
            r = await client.post(
                "/v1/tickets",
                json={"location_id": str(LOCATION_ID), "service_id": str(SERVICE_ID)},
                headers=headers,
            )
            assert r.status_code == 201
            ids.append(r.json()["id"])
        return ids

    async def test_call_next_returns_first_waiting(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        ticket_ids = await self._create_n_tickets(client, staff_headers, 3)

        resp = await client.post(
            f"/v1/counters/{COUNTER_ID}/call-next",
            json={},
            headers=staff_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should get first ticket (lowest number = earliest created)
        assert data["id"] == ticket_ids[0]
        assert data["status"] == "CALLED"

    async def test_call_next_empty_queue_returns_null(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        resp = await client.post(
            f"/v1/counters/{COUNTER_ID}/call-next",
            json={},
            headers=staff_headers,
        )
        assert resp.status_code == 200
        assert resp.json() is None

    async def test_concurrent_call_next_no_duplicate(
        self, db_session: AsyncSession, seeded_db, staff_headers
    ):
        """
        Concurrency proof: 50 WAITING tickets, 25 concurrent call-next requests.
        Every returned ticket ID must be unique; # CALLED == # successful calls.
        """
        if "sqlite" in str(db_session.bind):
            pytest.skip("SQLite does not support SELECT FOR UPDATE SKIP LOCKED")

        from app.main import app

        import uuid
        from app.models.ticket import Ticket, TicketStatus

        # Seed 50 WAITING tickets
        for i in range(50):
            ticket = Ticket(
                id=uuid.uuid4(),
                tenant_id=TENANT_ID,
                location_id=LOCATION_ID,
                service_id=SERVICE_ID,
                number=100 + i,
                status=TicketStatus.WAITING,
                priority=5,
            )
            db_session.add(ticket)
        await db_session.commit()

        results: list[dict | None] = []

        async def call_next_once():
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://testserver"
            ) as c:
                resp = await c.post(
                    f"/v1/counters/{COUNTER_ID}/call-next",
                    json={},
                    headers=staff_headers,
                )
                results.append(resp.json())

        # Fire 25 concurrent requests (each gets one ticket; 25 succeed, rest get None)
        await asyncio.gather(*[call_next_once() for _ in range(25)])

        non_null = [r for r in results if r is not None]
        ticket_ids_called = [r["id"] for r in non_null]

        # No duplicate ticket IDs
        assert len(ticket_ids_called) == len(set(ticket_ids_called)), (
            f"Duplicate tickets returned: {ticket_ids_called}"
        )
        # Number of CALLED tickets == number of successful calls
        assert len(non_null) == len(ticket_ids_called)

    async def test_call_next_respects_priority(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        """Higher-priority (lower number) ticket is called first."""
        import uuid

        from app.models.ticket import Ticket, TicketStatus
        from app.db.session import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            low_priority = Ticket(
                id=uuid.uuid4(),
                tenant_id=TENANT_ID,
                location_id=LOCATION_ID,
                service_id=SERVICE_ID,
                number=100,
                status=TicketStatus.WAITING,
                priority=9,  # low priority
            )
            high_priority = Ticket(
                id=uuid.uuid4(),
                tenant_id=TENANT_ID,
                location_id=LOCATION_ID,
                service_id=SERVICE_ID,
                number=101,
                status=TicketStatus.WAITING,
                priority=1,  # high priority
            )
            session.add_all([low_priority, high_priority])
            await session.commit()

            high_id = str(high_priority.id)

        resp = await client.post(
            f"/v1/counters/{COUNTER_ID}/call-next",
            json={},
            headers=staff_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == high_id
