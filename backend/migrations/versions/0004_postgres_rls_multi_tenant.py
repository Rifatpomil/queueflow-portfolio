"""Postgres Row-Level Security (RLS) for multi-tenant defense in depth.

Revision ID: 0004
Revises: 0003
Create Date: 2024-01-04 00:00:00.000000

When RLS_ENABLED=true, the app sets app.tenant_id (and optionally
app.signage_location_id for public signage) before each request.
Policies restrict rows to the current tenant.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Helper: current tenant from session variable ───────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION rls_current_tenant_id()
        RETURNS uuid AS $$
        BEGIN
            RETURN NULLIF(current_setting('app.tenant_id', true), '')::uuid;
        EXCEPTION WHEN OTHERS THEN
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql STABLE;
    """)

    op.execute("""
        CREATE OR REPLACE FUNCTION rls_current_signage_location_id()
        RETURNS uuid AS $$
        BEGIN
            RETURN NULLIF(current_setting('app.signage_location_id', true), '')::uuid;
        EXCEPTION WHEN OTHERS THEN
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql STABLE;
    """)

    # ── RLS on tickets ────────────────────────────────────────────────────────
    # When app.tenant_id is NULL (RLS_ENABLED=false), allow all for backward compat
    op.execute("ALTER TABLE tickets ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tickets_tenant_isolation ON tickets
        FOR ALL
        USING (
            rls_current_tenant_id() IS NULL
            OR tenant_id = rls_current_tenant_id()
            OR (rls_current_signage_location_id() IS NOT NULL AND location_id = rls_current_signage_location_id())
        )
        WITH CHECK (
            rls_current_tenant_id() IS NULL
            OR tenant_id = rls_current_tenant_id()
        )
    """)

    # ── RLS on ticket_events (via ticket.tenant_id) ────────────────────────────
    op.execute("ALTER TABLE ticket_events ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY ticket_events_tenant_isolation ON ticket_events
        FOR ALL
        USING (
            rls_current_tenant_id() IS NULL
            OR EXISTS (
                SELECT 1 FROM tickets t
                WHERE t.id = ticket_events.ticket_id
                AND (t.tenant_id = rls_current_tenant_id()
                     OR (rls_current_signage_location_id() IS NOT NULL AND t.location_id = rls_current_signage_location_id()))
            )
        )
        WITH CHECK (
            rls_current_tenant_id() IS NULL
            OR EXISTS (
                SELECT 1 FROM tickets t
                WHERE t.id = ticket_events.ticket_id
                AND t.tenant_id = rls_current_tenant_id()
            )
        )
    """)

    # ── RLS on locations ──────────────────────────────────────────────────────
    op.execute("ALTER TABLE locations ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY locations_tenant_isolation ON locations
        FOR ALL
        USING (
            rls_current_tenant_id() IS NULL
            OR tenant_id = rls_current_tenant_id()
            OR (rls_current_signage_location_id() IS NOT NULL AND id = rls_current_signage_location_id())
        )
        WITH CHECK (
            rls_current_tenant_id() IS NULL
            OR tenant_id = rls_current_tenant_id()
        )
    """)

    # ── RLS on idempotency_keys ────────────────────────────────────────────────
    op.execute("ALTER TABLE idempotency_keys ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY idempotency_keys_tenant_isolation ON idempotency_keys
        FOR ALL
        USING (
            rls_current_tenant_id() IS NULL
            OR tenant_id = rls_current_tenant_id()
        )
        WITH CHECK (
            rls_current_tenant_id() IS NULL
            OR tenant_id = rls_current_tenant_id()
        )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS idempotency_keys_tenant_isolation ON idempotency_keys")
    op.execute("ALTER TABLE idempotency_keys DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS locations_tenant_isolation ON locations")
    op.execute("ALTER TABLE locations DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS ticket_events_tenant_isolation ON ticket_events")
    op.execute("ALTER TABLE ticket_events DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tickets_tenant_isolation ON tickets")
    op.execute("ALTER TABLE tickets DISABLE ROW LEVEL SECURITY")

    op.execute("DROP FUNCTION IF EXISTS rls_current_signage_location_id()")
    op.execute("DROP FUNCTION IF EXISTS rls_current_tenant_id()")
