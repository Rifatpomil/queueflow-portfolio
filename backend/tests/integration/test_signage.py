"""Integration tests: signage snapshot endpoint."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import COUNTER_ID, LOCATION_ID, SERVICE_ID


@pytest.mark.asyncio
class TestSignage:
    async def test_snapshot_requires_no_auth(self, client: AsyncClient, seeded_db):
        """Signage is a public endpoint."""
        resp = await client.get(f"/v1/signage/{LOCATION_ID}")
        assert resp.status_code == 200

    async def test_snapshot_empty_queue(self, client: AsyncClient, seeded_db):
        resp = await client.get(f"/v1/signage/{LOCATION_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["waiting_count"] == 0
        assert data["now_serving"] == []
        assert data["recently_called"] == []

    async def test_snapshot_reflects_created_ticket(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        # Create a ticket
        await client.post(
            "/v1/tickets",
            json={"location_id": str(LOCATION_ID)},
            headers=staff_headers,
        )

        resp = await client.get(f"/v1/signage/{LOCATION_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["waiting_count"] == 1

    async def test_snapshot_after_call_next(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        # Create and call a ticket
        await client.post(
            "/v1/tickets",
            json={"location_id": str(LOCATION_ID), "service_id": str(SERVICE_ID)},
            headers=staff_headers,
        )
        await client.post(
            f"/v1/counters/{COUNTER_ID}/call-next",
            json={},
            headers=staff_headers,
        )

        resp = await client.get(f"/v1/signage/{LOCATION_ID}")
        data = resp.json()
        # Ticket moved from waiting → called
        assert data["waiting_count"] == 0
        assert len(data["recently_called"]) == 1

    async def test_snapshot_location_not_found(self, client: AsyncClient, seeded_db):
        import uuid
        resp = await client.get(f"/v1/signage/{uuid.uuid4()}")
        assert resp.status_code == 404

    async def test_snapshot_has_required_fields(self, client: AsyncClient, seeded_db):
        resp = await client.get(f"/v1/signage/{LOCATION_ID}")
        data = resp.json()
        required_fields = {
            "location_id", "location_name", "now_serving", "recently_called",
            "waiting_count", "snapshot_at",
        }
        assert required_fields.issubset(data.keys())

    async def test_snapshot_relationship_fields_populated(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        """
        Regression test for the selectinload fix (G1).

        After a ticket is CALLED, the snapshot entry must have counter_name
        and service_name populated. These fields come from eagerly-loaded
        relationships — without selectinload they would raise MissingGreenlet
        in an async SQLAlchemy session.
        """
        # Create a ticket
        await client.post(
            "/v1/tickets",
            json={"location_id": str(LOCATION_ID), "service_id": str(SERVICE_ID)},
            headers=staff_headers,
        )
        # Call it (assigns the counter)
        call_resp = await client.post(
            f"/v1/counters/{COUNTER_ID}/call-next",
            json={},
            headers=staff_headers,
        )
        assert call_resp.json()["status"] == "CALLED"

        # Verify snapshot entry has the relationship-backed fields
        snap = await client.get(f"/v1/signage/{LOCATION_ID}")
        assert snap.status_code == 200
        data = snap.json()
        assert len(data["recently_called"]) == 1
        entry = data["recently_called"][0]
        # counter_name comes from Ticket.assigned_counter (selectinload)
        assert entry["counter_name"] == "Counter 1"
        # service_name comes from Ticket.service (selectinload)
        assert entry["service_name"] == "General"
