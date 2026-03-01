"""DB-level state machine enforcement + immutable event log + call-next index.

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-03 00:00:00.000000

P0 Portfolio requirements:
- Trigger rejects illegal ticket status transitions at DB level
- Trigger prevents UPDATE/DELETE on ticket_events (append-only)
- Index for atomic call-next query (location_id, status, priority, created_at)
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── State machine: reject illegal ticket status transitions ─────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION check_ticket_status_transition()
        RETURNS TRIGGER AS $$
        BEGIN
            IF OLD.status IS DISTINCT FROM NEW.status THEN
                CASE OLD.status
                    WHEN 'CREATED' THEN
                        IF NEW.status NOT IN ('WAITING', 'CANCELED') THEN
                            RAISE EXCEPTION 'Invalid transition: % -> %', OLD.status, NEW.status;
                        END IF;
                    WHEN 'WAITING' THEN
                        IF NEW.status NOT IN ('CALLED', 'CANCELED', 'NO_SHOW') THEN
                            RAISE EXCEPTION 'Invalid transition: % -> %', OLD.status, NEW.status;
                        END IF;
                    WHEN 'CALLED' THEN
                        IF NEW.status NOT IN ('IN_SERVICE', 'WAITING', 'NO_SHOW', 'CANCELED') THEN
                            RAISE EXCEPTION 'Invalid transition: % -> %', OLD.status, NEW.status;
                        END IF;
                    WHEN 'IN_SERVICE' THEN
                        IF NEW.status NOT IN ('COMPLETED', 'HOLD', 'TRANSFERRED', 'CANCELED') THEN
                            RAISE EXCEPTION 'Invalid transition: % -> %', OLD.status, NEW.status;
                        END IF;
                    WHEN 'HOLD' THEN
                        IF NEW.status NOT IN ('WAITING', 'CANCELED') THEN
                            RAISE EXCEPTION 'Invalid transition: % -> %', OLD.status, NEW.status;
                        END IF;
                    WHEN 'TRANSFERRED' THEN
                        IF NEW.status != 'WAITING' THEN
                            RAISE EXCEPTION 'Invalid transition: % -> %', OLD.status, NEW.status;
                        END IF;
                    WHEN 'COMPLETED', 'CANCELED', 'NO_SHOW' THEN
                        RAISE EXCEPTION 'Terminal state % cannot transition to %', OLD.status, NEW.status;
                    ELSE
                        RAISE EXCEPTION 'Unknown status: %', OLD.status;
                END CASE;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_tickets_status_transition
            BEFORE UPDATE ON tickets
            FOR EACH ROW
            EXECUTE FUNCTION check_ticket_status_transition();
    """)

    # ── Event log: append-only (no UPDATE/DELETE) ──────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_ticket_events_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'ticket_events is append-only: % not allowed', TG_OP;
        END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("""
        CREATE TRIGGER trg_ticket_events_immutable
            BEFORE UPDATE OR DELETE ON ticket_events
            FOR EACH ROW
            EXECUTE FUNCTION prevent_ticket_events_mutation();
    """)

    # ── Index for atomic call-next (ORDER BY priority, created_at) ──────────────
    op.create_index(
        "ix_tickets_location_status_priority_created",
        "tickets",
        ["location_id", "status", "priority", "created_at"],
    )

    # ── Analytics: p95 wait, throughput, queue depth timeseries ──────────────────
    op.create_index(
        "ix_tickets_location_created",
        "tickets",
        ["location_id", "created_at"],
    )
    op.execute("""
        CREATE INDEX ix_tickets_location_created_called
        ON tickets (location_id, created_at)
        WHERE called_at IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX ix_tickets_location_created_completed
        ON tickets (location_id, created_at)
        WHERE status = 'COMPLETED'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tickets_location_created_completed")
    op.execute("DROP INDEX IF EXISTS ix_tickets_location_created_called")
    op.drop_index(
        "ix_tickets_location_created",
        table_name="tickets",
    )
    op.drop_index(
        "ix_tickets_location_status_priority_created",
        table_name="tickets",
    )
    op.execute("DROP TRIGGER IF EXISTS trg_ticket_events_immutable ON ticket_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_ticket_events_mutation()")
    op.execute("DROP TRIGGER IF EXISTS trg_tickets_status_transition ON tickets")
    op.execute("DROP FUNCTION IF EXISTS check_ticket_status_transition()")
