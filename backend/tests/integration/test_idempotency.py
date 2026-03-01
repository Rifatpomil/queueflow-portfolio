"""Integration tests: idempotency key behaviour."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from tests.conftest import COUNTER_ID, LOCATION_ID, SERVICE_ID


@pytest.mark.asyncio
class TestIdempotency:
    async def test_same_key_same_body_returns_same_ticket(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        key = "idem-001"
        body = {"location_id": str(LOCATION_ID), "service_id": str(SERVICE_ID)}

        r1 = await client.post(
            "/v1/tickets",
            json=body,
            headers={**staff_headers, "Idempotency-Key": key},
        )
        r2 = await client.post(
            "/v1/tickets",
            json=body,
            headers={**staff_headers, "Idempotency-Key": key},
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] == r2.json()["id"]
        assert r1.json()["number"] == r2.json()["number"]

    async def test_different_keys_create_different_tickets(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        body = {"location_id": str(LOCATION_ID)}
        r1 = await client.post(
            "/v1/tickets",
            json=body,
            headers={**staff_headers, "Idempotency-Key": "key-alpha"},
        )
        r2 = await client.post(
            "/v1/tickets",
            json=body,
            headers={**staff_headers, "Idempotency-Key": "key-beta"},
        )
        assert r1.status_code == 201
        assert r2.status_code == 201
        assert r1.json()["id"] != r2.json()["id"]

    async def test_no_key_always_creates_new_ticket(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        body = {"location_id": str(LOCATION_ID)}
        r1 = await client.post("/v1/tickets", json=body, headers=staff_headers)
        r2 = await client.post("/v1/tickets", json=body, headers=staff_headers)
        assert r1.json()["id"] != r2.json()["id"]

    async def test_call_next_idempotency(
        self, client: AsyncClient, seeded_db, staff_headers
    ):
        """Same Idempotency-Key on call-next returns same ticket."""
        # Create one ticket
        await client.post(
            "/v1/tickets",
            json={"location_id": str(LOCATION_ID), "service_id": str(SERVICE_ID)},
            headers=staff_headers,
        )
        key = "call-next-idem-001"
        r1 = await client.post(
            f"/v1/counters/{COUNTER_ID}/call-next",
            json={},
            headers={**staff_headers, "Idempotency-Key": key},
        )
        r2 = await client.post(
            f"/v1/counters/{COUNTER_ID}/call-next",
            json={},
            headers={**staff_headers, "Idempotency-Key": key},
        )
        assert r1.status_code == 200
        assert r2.status_code == 200
        # First call gets the ticket; second returns same (idempotent)
        assert r1.json()["id"] == r2.json()["id"]
