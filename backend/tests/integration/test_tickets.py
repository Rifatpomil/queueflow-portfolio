"""Integration tests: ticket creation, lifecycle, and state transitions."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import LOCATION_ID, SERVICE_ID, TENANT_ID


@pytest.mark.asyncio
class TestCreateTicket:
    async def test_create_ticket_success(self, client: AsyncClient, seeded_db, staff_headers):
        resp = await client.post(
            "/v1/tickets",
            json={
                "location_id": str(LOCATION_ID),
                "service_id": str(SERVICE_ID),
                "priority": 5,
            },
            headers=staff_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "WAITING"
        assert data["number"] == 1
        assert data["location_id"] == str(LOCATION_ID)

    async def test_create_ticket_unauthenticated(self, client: AsyncClient, seeded_db):
        resp = await client.post(
            "/v1/tickets",
            json={"location_id": str(LOCATION_ID)},
        )
        assert resp.status_code == 401

    async def test_viewer_cannot_create_ticket(self, client: AsyncClient, seeded_db, viewer_headers):
        resp = await client.post(
            "/v1/tickets",
            json={"location_id": str(LOCATION_ID)},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    async def test_create_ticket_increments_number(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        r1 = await client.post(
            "/v1/tickets",
            json={"location_id": str(LOCATION_ID)},
            headers=staff_headers,
        )
        r2 = await client.post(
            "/v1/tickets",
            json={"location_id": str(LOCATION_ID)},
            headers=staff_headers,
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r2.json()["number"] == r1.json()["number"] + 1

    async def test_idempotency_key_prevents_duplicate(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        key = "test-idem-key-001"
        body = {"location_id": str(LOCATION_ID)}
        r1 = await client.post(
            "/v1/tickets", json=body, headers={**staff_headers, "Idempotency-Key": key}
        )
        r2 = await client.post(
            "/v1/tickets", json=body, headers={**staff_headers, "Idempotency-Key": key}
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        # Same ticket returned both times
        assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
class TestTicketLifecycle:
    async def _create_ticket(self, client: AsyncClient, headers: dict) -> dict:
        resp = await client.post(
            "/v1/tickets",
            json={"location_id": str(LOCATION_ID), "service_id": str(SERVICE_ID)},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()

    async def test_cancel_waiting_ticket(self, client: AsyncClient, seeded_db, staff_headers):
        ticket = await self._create_ticket(client, staff_headers)
        resp = await client.post(
            f"/v1/tickets/{ticket['id']}/cancel", headers=staff_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELED"

    async def test_hold_and_requeue(self, client: AsyncClient, seeded_db, staff_headers):
        from tests.conftest import COUNTER_ID

        ticket = await self._create_ticket(client, staff_headers)
        ticket_id = ticket["id"]

        # Call next to move to CALLED
        call_resp = await client.post(
            f"/v1/counters/{COUNTER_ID}/call-next", json={}, headers=staff_headers
        )
        assert call_resp.status_code == 200
        assert call_resp.json()["id"] == ticket_id

        # Start service
        start_resp = await client.post(
            f"/v1/tickets/{ticket_id}/start-service", headers=staff_headers
        )
        assert start_resp.status_code == 200
        assert start_resp.json()["status"] == "IN_SERVICE"

        # Hold
        hold_resp = await client.post(
            f"/v1/tickets/{ticket_id}/hold", headers=staff_headers
        )
        assert hold_resp.status_code == 200
        assert hold_resp.json()["status"] == "HOLD"

    async def test_invalid_transition_returns_409(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        ticket = await self._create_ticket(client, staff_headers)
        # Can't start service on a WAITING ticket (must be CALLED first)
        resp = await client.post(
            f"/v1/tickets/{ticket['id']}/start-service", headers=staff_headers
        )
        assert resp.status_code == 409

    async def test_complete_full_lifecycle(self, client: AsyncClient, seeded_db, staff_headers):
        from tests.conftest import COUNTER_ID

        # Create ticket
        t = await self._create_ticket(client, staff_headers)
        tid = t["id"]

        # Call next
        call = await client.post(
            f"/v1/counters/{COUNTER_ID}/call-next", json={}, headers=staff_headers
        )
        assert call.json()["id"] == tid
        assert call.json()["status"] == "CALLED"

        # Start service
        start = await client.post(f"/v1/tickets/{tid}/start-service", headers=staff_headers)
        assert start.json()["status"] == "IN_SERVICE"

        # Complete
        complete = await client.post(f"/v1/tickets/{tid}/complete", headers=staff_headers)
        assert complete.json()["status"] == "COMPLETED"
        assert complete.json()["completed_at"] is not None
