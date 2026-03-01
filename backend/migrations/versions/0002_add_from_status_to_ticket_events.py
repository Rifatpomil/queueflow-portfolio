"""Add from_status column to ticket_events for explicit audit trail.

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 00:00:00.000000

Rationale
---------
Previously the event log recorded *what happened* (event_type) but not
*where the ticket came from*. Answering "how long did this ticket spend in
CALLED state?" required replaying the entire event chain. The new
``from_status`` column stores the previous status alongside every event,
making point-in-time transition queries trivial:

    SELECT event_type, from_status, occurred_at
    FROM ticket_events
    WHERE ticket_id = :id
    ORDER BY occurred_at;
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "ticket_events",
        sa.Column("from_status", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ticket_events", "from_status")
