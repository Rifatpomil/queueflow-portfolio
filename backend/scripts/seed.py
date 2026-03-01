#!/usr/bin/env python3
"""
Seed demo data – creates a complete demo environment:

  Tenant:    Acme Services
  Location:  Downtown Office (timezone: America/Vancouver)
  Services:  General Inquiry (G), Permits & Licensing (P), VIP (V)
  Counters:  Counter 1, Counter 2, Counter 3
  Channels:  Walk-in, Phone
  Users:     admin, manager, staff, viewer (all @queueflow.dev)
  Roles:     admin, manager, staff, viewer
  Tickets:   20 demo tickets in various states
"""
from __future__ import annotations

import asyncio
import sys
import os
import uuid
from datetime import datetime, timedelta, timezone

# Ensure app is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.models import *  # noqa: F401, F403

settings = get_settings()

TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
LOCATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000020")
SERVICE_GENERAL_ID = uuid.UUID("00000000-0000-0000-0000-000000000031")
SERVICE_PERMITS_ID = uuid.UUID("00000000-0000-0000-0000-000000000032")
SERVICE_VIP_ID = uuid.UUID("00000000-0000-0000-0000-000000000033")
COUNTER_1_ID = uuid.UUID("00000000-0000-0000-0000-000000000041")
COUNTER_2_ID = uuid.UUID("00000000-0000-0000-0000-000000000042")
COUNTER_3_ID = uuid.UUID("00000000-0000-0000-0000-000000000043")
CHANNEL_WALKIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000051")
CHANNEL_PHONE_ID = uuid.UUID("00000000-0000-0000-0000-000000000052")
ADMIN_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
MANAGER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")
STAFF_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
VIEWER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000004")
ROLE_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000061")
ROLE_MANAGER_ID = uuid.UUID("00000000-0000-0000-0000-000000000062")
ROLE_STAFF_ID = uuid.UUID("00000000-0000-0000-0000-000000000063")
ROLE_VIEWER_ID = uuid.UUID("00000000-0000-0000-0000-000000000064")


async def seed() -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        from sqlalchemy import text, select
        from app.models.tenant import Tenant
        from app.models.location import Location
        from app.models.service import Service
        from app.models.counter import Counter
        from app.models.channel import Channel
        from app.models.user import User, Role, UserRole
        from app.models.ticket import Ticket, TicketStatus
        from app.models.ticket_event import TicketEvent, EventType

        # Idempotency: skip if already seeded
        existing = await session.get(Tenant, TENANT_ID)
        if existing:
            print("Demo data already seeded. Skipping.")
            return

        now = datetime.now(tz=timezone.utc)

        # ── Tenant ─────────────────────────────────────────────────────────────
        tenant = Tenant(id=TENANT_ID, name="Acme Services", slug="acme-services")
        session.add(tenant)

        # ── Location ───────────────────────────────────────────────────────────
        location = Location(
            id=LOCATION_ID,
            tenant_id=TENANT_ID,
            name="Downtown Office",
            address="123 Main Street, Vancouver, BC",
            timezone="America/Vancouver",
        )
        session.add(location)

        # ── Services ───────────────────────────────────────────────────────────
        for sid, name, prefix, category in [
            (SERVICE_GENERAL_ID, "General Inquiry", "G", "general"),
            (SERVICE_PERMITS_ID, "Permits & Licensing", "P", "permits"),
            (SERVICE_VIP_ID, "VIP / Priority", "V", "vip"),
        ]:
            session.add(Service(
                id=sid, tenant_id=TENANT_ID, location_id=LOCATION_ID,
                name=name, prefix=prefix, category=category,
            ))

        # ── Counters ───────────────────────────────────────────────────────────
        for cid, name in [
            (COUNTER_1_ID, "Counter 1"),
            (COUNTER_2_ID, "Counter 2"),
            (COUNTER_3_ID, "Counter 3"),
        ]:
            session.add(Counter(id=cid, location_id=LOCATION_ID, name=name))

        # ── Channels ───────────────────────────────────────────────────────────
        session.add(Channel(id=CHANNEL_WALKIN_ID, tenant_id=TENANT_ID, name="Walk-in"))
        session.add(Channel(id=CHANNEL_PHONE_ID, tenant_id=TENANT_ID, name="Phone"))

        # ── Roles ──────────────────────────────────────────────────────────────
        for rid, rname, rdesc in [
            (ROLE_ADMIN_ID, "admin", "Full system access"),
            (ROLE_MANAGER_ID, "manager", "Location management"),
            (ROLE_STAFF_ID, "staff", "Queue operations"),
            (ROLE_VIEWER_ID, "viewer", "Read-only / signage"),
        ]:
            session.add(Role(id=rid, tenant_id=TENANT_ID, name=rname, description=rdesc))

        # ── Users ──────────────────────────────────────────────────────────────
        for uid, email, display, role_id in [
            (ADMIN_USER_ID, "admin@queueflow.dev", "System Admin", ROLE_ADMIN_ID),
            (MANAGER_USER_ID, "manager@queueflow.dev", "Location Manager", ROLE_MANAGER_ID),
            (STAFF_USER_ID, "staff@queueflow.dev", "Staff Member", ROLE_STAFF_ID),
            (VIEWER_USER_ID, "viewer@queueflow.dev", "Signage Viewer", ROLE_VIEWER_ID),
        ]:
            user = User(
                id=uid,
                tenant_id=TENANT_ID,
                email=email,
                display_name=display,
                hashed_password=hash_password("demo-password"),
            )
            session.add(user)
            await session.flush()
            session.add(UserRole(user_id=uid, role_id=role_id))

        await session.flush()

        # ── Demo tickets ────────────────────────────────────────────────────────
        statuses_services = [
            # (number, status, service_id, priority, minutes_ago, counter)
            (1,  "IN_SERVICE",  SERVICE_GENERAL_ID, 5, 15, COUNTER_1_ID),
            (2,  "IN_SERVICE",  SERVICE_PERMITS_ID, 3, 20, COUNTER_2_ID),
            (3,  "CALLED",      SERVICE_GENERAL_ID, 5, 5,  COUNTER_3_ID),
            (4,  "CALLED",      SERVICE_VIP_ID,     1, 3,  COUNTER_1_ID),
            (5,  "WAITING",     SERVICE_GENERAL_ID, 5, 2,  None),
            (6,  "WAITING",     SERVICE_GENERAL_ID, 5, 4,  None),
            (7,  "WAITING",     SERVICE_PERMITS_ID, 5, 6,  None),
            (8,  "WAITING",     SERVICE_GENERAL_ID, 5, 8,  None),
            (9,  "WAITING",     SERVICE_VIP_ID,     2, 1,  None),
            (10, "WAITING",     SERVICE_GENERAL_ID, 5, 10, None),
            (11, "WAITING",     SERVICE_PERMITS_ID, 5, 12, None),
            (12, "WAITING",     SERVICE_GENERAL_ID, 7, 7,  None),
            (13, "COMPLETED",   SERVICE_GENERAL_ID, 5, 60, None),
            (14, "COMPLETED",   SERVICE_PERMITS_ID, 5, 90, None),
            (15, "COMPLETED",   SERVICE_VIP_ID,     1, 75, None),
            (16, "COMPLETED",   SERVICE_GENERAL_ID, 5, 50, None),
            (17, "CANCELED",    SERVICE_GENERAL_ID, 5, 45, None),
            (18, "NO_SHOW",     SERVICE_GENERAL_ID, 5, 30, None),
            (19, "WAITING",     SERVICE_GENERAL_ID, 5, 3,  None),
            (20, "WAITING",     SERVICE_PERMITS_ID, 4, 5,  None),
        ]

        for num, tstatus, svc_id, priority, mins_ago, counter_id in statuses_services:
            created = now - timedelta(minutes=mins_ago)
            called_at = created + timedelta(minutes=2) if tstatus in (
                "CALLED", "IN_SERVICE", "COMPLETED", "CANCELED", "NO_SHOW"
            ) else None
            svc_started = called_at + timedelta(minutes=1) if tstatus in (
                "IN_SERVICE", "COMPLETED"
            ) else None
            completed_at = svc_started + timedelta(minutes=5) if tstatus == "COMPLETED" else None

            t = Ticket(
                id=uuid.uuid4(),
                tenant_id=TENANT_ID,
                location_id=LOCATION_ID,
                service_id=svc_id,
                channel_id=CHANNEL_WALKIN_ID,
                assigned_counter_id=counter_id,
                number=num,
                status=tstatus,
                priority=priority,
                created_at=created,
                updated_at=created,
                called_at=called_at,
                service_started_at=svc_started,
                completed_at=completed_at,
            )
            session.add(t)
            await session.flush()

            session.add(TicketEvent(
                ticket_id=t.id,
                event_type=EventType.CREATED,
                occurred_at=created,
            ))
            if called_at:
                session.add(TicketEvent(
                    ticket_id=t.id,
                    event_type=EventType.CALLED,
                    actor_user_id=STAFF_USER_ID,
                    occurred_at=called_at,
                ))
            if svc_started:
                session.add(TicketEvent(
                    ticket_id=t.id,
                    event_type=EventType.IN_SERVICE,
                    actor_user_id=STAFF_USER_ID,
                    occurred_at=svc_started,
                ))
            if completed_at:
                session.add(TicketEvent(
                    ticket_id=t.id,
                    event_type=EventType.COMPLETED,
                    actor_user_id=STAFF_USER_ID,
                    occurred_at=completed_at,
                ))

        await session.commit()
        print("✓ Demo data seeded successfully!")
        print(f"\nDemo users (DEV JWT via POST /dev/login):")
        print(f"  admin@queueflow.dev   – admin role")
        print(f"  manager@queueflow.dev – manager role")
        print(f"  staff@queueflow.dev   – staff role")
        print(f"  viewer@queueflow.dev  – viewer role")
        print(f"\nDemo tenant ID:   {TENANT_ID}")
        print(f"Demo location ID: {LOCATION_ID}")
        print(f"\nSignage stream: GET /v1/signage/{LOCATION_ID}")
        print(f"Signage SSE:    GET /v1/signage/{LOCATION_ID}/stream")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
