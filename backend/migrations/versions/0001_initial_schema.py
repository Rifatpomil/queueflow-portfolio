"""Initial schema – all tables, constraints, and indexes.

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── tenants ────────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # ── locations ──────────────────────────────────────────────────────────────
    op.create_table(
        "locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("address", sa.String(500)),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_locations_tenant_id", "locations", ["tenant_id"])

    # ── services ───────────────────────────────────────────────────────────────
    op.create_table(
        "services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("prefix", sa.String(10), nullable=False, server_default="G"),
        sa.Column("category", sa.String(100)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("avg_service_minutes", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_services_tenant_id", "services", ["tenant_id"])
    op.create_index("ix_services_location_id", "services", ["location_id"])

    # ── counters ───────────────────────────────────────────────────────────────
    op.create_table(
        "counters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("counter_type", sa.String(50), nullable=False, server_default="standard"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_counters_location_id", "counters", ["location_id"])

    # ── channels ───────────────────────────────────────────────────────────────
    op.create_table(
        "channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_channels_tenant_id", "channels", ["tenant_id"])

    # ── roles ──────────────────────────────────────────────────────────────────
    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("description", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )
    op.create_index("ix_roles_tenant_id", "roles", ["tenant_id"])

    # ── users ──────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255)),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_email", "users", ["email"])

    # ── user_roles ─────────────────────────────────────────────────────────────
    op.create_table(
        "user_roles",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])

    # ── tickets ────────────────────────────────────────────────────────────────
    op.create_table(
        "tickets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("service_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("channel_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_counter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="WAITING"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("called_at", sa.DateTime(timezone=True)),
        sa.Column("service_started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"]),
        sa.ForeignKeyConstraint(["assigned_counter_id"], ["counters.id"]),
        # Enforce valid status values
        sa.CheckConstraint(
            "status IN ('CREATED','WAITING','CALLED','IN_SERVICE','HOLD',"
            "'TRANSFERRED','COMPLETED','CANCELED','NO_SHOW')",
            name="ck_tickets_valid_status",
        ),
        sa.CheckConstraint("priority BETWEEN 1 AND 10", name="ck_tickets_priority_range"),
    )
    # Covering index for call-next query (location + WAITING, ordered by priority + created_at)
    op.create_index(
        "ix_tickets_location_status_created",
        "tickets",
        ["location_id", "status", "created_at"],
    )
    # Service-filtered queue queries
    op.create_index(
        "ix_tickets_service_status_created",
        "tickets",
        ["service_id", "status", "created_at"],
    )
    op.create_index("ix_tickets_tenant_id", "tickets", ["tenant_id"])
    # Display number lookup
    op.create_index("ix_tickets_number_location", "tickets", ["number", "location_id"])

    # ── ticket_events ──────────────────────────────────────────────────────────
    op.create_table(
        "ticket_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload_json", postgresql.JSONB),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_ticket_events_ticket_occurred",
        "ticket_events",
        ["ticket_id", "occurred_at"],
    )

    # ── interactions ───────────────────────────────────────────────────────────
    op.create_table(
        "interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticket_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("counter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("outcome", sa.String(30)),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["counter_id"], ["counters.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_interactions_counter_started", "interactions", ["counter_id", "started_at"]
    )
    op.create_index("ix_interactions_ticket_id", "interactions", ["ticket_id"])

    # ── idempotency_keys ───────────────────────────────────────────────────────
    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True)),
        sa.Column("response_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "key", name="uq_idempotency_tenant_key"),
    )
    op.create_index("ix_idempotency_tenant_key", "idempotency_keys", ["tenant_id", "key"])
    op.create_index("ix_idempotency_expires_at", "idempotency_keys", ["expires_at"])

    # ── audit_log ──────────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("object_type", sa.String(100), nullable=False),
        sa.Column("object_id", sa.String(255)),
        sa.Column("before_json", postgresql.JSONB),
        sa.Column("after_json", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_audit_log_tenant_created", "audit_log", ["tenant_id", "created_at"])
    op.create_index("ix_audit_log_object", "audit_log", ["object_type", "object_id"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("idempotency_keys")
    op.drop_table("interactions")
    op.drop_table("ticket_events")
    op.drop_table("tickets")
    op.drop_table("user_roles")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("channels")
    op.drop_table("counters")
    op.drop_table("services")
    op.drop_table("locations")
    op.drop_table("tenants")
