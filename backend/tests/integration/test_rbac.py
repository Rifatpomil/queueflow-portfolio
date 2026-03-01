"""
Integration tests: RBAC enforcement.

Verifies that:
- viewer role is forbidden from all write operations (403)
- viewer role can read tickets and analytics (200)
- staff role can perform all ticket lifecycle operations
- unauthenticated requests get 401
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import COUNTER_ID, LOCATION_ID, SERVICE_ID, TENANT_ID


@pytest.mark.asyncio
class TestRBAC:
    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _create_ticket(self, client: AsyncClient, headers: dict) -> str:
        resp = await client.post(
            "/v1/tickets",
            json={"location_id": str(LOCATION_ID), "service_id": str(SERVICE_ID)},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["id"]

    # ── Unauthenticated (no token) ────────────────────────────────────────────

    async def test_unauthenticated_create_ticket_returns_401(
        self, client: AsyncClient, seeded_db
    ):
        resp = await client.post(
            "/v1/tickets",
            json={"location_id": str(LOCATION_ID)},
        )
        assert resp.status_code == 401

    async def test_unauthenticated_list_tickets_returns_401(
        self, client: AsyncClient, seeded_db
    ):
        resp = await client.get(f"/v1/tickets?location_id={LOCATION_ID}")
        assert resp.status_code == 401

    # ── Viewer: read allowed, writes forbidden ────────────────────────────────

    async def test_viewer_can_list_tickets(
        self, client: AsyncClient, seeded_db, viewer_headers
    ):
        resp = await client.get(
            f"/v1/tickets?location_id={LOCATION_ID}", headers=viewer_headers
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_viewer_cannot_create_ticket(
        self, client: AsyncClient, seeded_db, viewer_headers
    ):
        resp = await client.post(
            "/v1/tickets",
            json={"location_id": str(LOCATION_ID), "service_id": str(SERVICE_ID)},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_call_next(
        self, client: AsyncClient, seeded_db, staff_headers, viewer_headers
    ):
        # Create a ticket first (as staff)
        await self._create_ticket(client, staff_headers)
        # Attempt call-next as viewer
        resp = await client.post(
            f"/v1/counters/{COUNTER_ID}/call-next",
            json={},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_cancel_ticket(
        self, client: AsyncClient, seeded_db, staff_headers, viewer_headers
    ):
        ticket_id = await self._create_ticket(client, staff_headers)
        resp = await client.post(
            f"/v1/tickets/{ticket_id}/cancel",
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    async def test_viewer_cannot_hold_ticket(
        self, client: AsyncClient, seeded_db, staff_headers, viewer_headers
    ):
        ticket_id = await self._create_ticket(client, staff_headers)
        resp = await client.post(
            f"/v1/tickets/{ticket_id}/hold",
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    # ── Staff: full lifecycle ─────────────────────────────────────────────────

    async def test_staff_full_lifecycle(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        """Staff can create → call-next → start-service → complete."""
        ticket_id = await self._create_ticket(client, staff_headers)

        # call-next
        call_resp = await client.post(
            f"/v1/counters/{COUNTER_ID}/call-next",
            json={},
            headers=staff_headers,
        )
        assert call_resp.status_code == 200
        assert call_resp.json()["status"] == "CALLED"
        assert call_resp.json()["id"] == ticket_id

        # start-service
        start_resp = await client.post(
            f"/v1/tickets/{ticket_id}/start-service",
            headers=staff_headers,
        )
        assert start_resp.status_code == 200
        assert start_resp.json()["status"] == "IN_SERVICE"

        # complete
        done_resp = await client.post(
            f"/v1/tickets/{ticket_id}/complete",
            headers=staff_headers,
        )
        assert done_resp.status_code == 200
        assert done_resp.json()["status"] == "COMPLETED"

    # ── Signage: public, no auth required ─────────────────────────────────────

    async def test_signage_snapshot_no_auth(
        self, client: AsyncClient, seeded_db
    ):
        """Signage snapshot endpoint is public — no Authorization header needed."""
        resp = await client.get(f"/v1/signage/{LOCATION_ID}")
        assert resp.status_code == 200
        data = resp.json()
        assert "now_serving" in data
        assert "recently_called" in data
        assert "waiting_count" in data
