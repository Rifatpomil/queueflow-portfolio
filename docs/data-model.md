# Data Model

## Entity-Relationship Diagram

```mermaid
erDiagram
    TENANTS {
        uuid id PK
        string name UK
        string slug UK
        bool active
        timestamptz created_at
    }
    LOCATIONS {
        uuid id PK
        uuid tenant_id FK
        string name
        string timezone
        bool active
    }
    SERVICES {
        uuid id PK
        uuid tenant_id FK
        uuid location_id FK "nullable"
        string name
        string prefix
        string category
        bool active
    }
    COUNTERS {
        uuid id PK
        uuid location_id FK
        string name
        string counter_type
        bool active
    }
    CHANNELS {
        uuid id PK
        uuid tenant_id FK
        string name
    }
    USERS {
        uuid id PK
        uuid tenant_id FK
        string email
        string display_name
        string hashed_password "nullable"
        string status
    }
    ROLES {
        uuid id PK
        uuid tenant_id FK
        string name
    }
    USER_ROLES {
        uuid user_id PK,FK
        uuid role_id PK,FK
        uuid location_id FK "nullable – scope to location"
    }
    TICKETS {
        uuid id PK
        uuid tenant_id FK
        uuid location_id FK
        uuid service_id FK "nullable"
        uuid channel_id FK "nullable"
        uuid assigned_counter_id FK "nullable"
        int number "display number per location"
        string status
        int priority "1=high, 10=low"
        timestamptz created_at
        timestamptz called_at
        timestamptz service_started_at
        timestamptz completed_at
    }
    TICKET_EVENTS {
        uuid id PK
        uuid ticket_id FK
        string event_type
        uuid actor_user_id FK "nullable"
        jsonb payload_json
        timestamptz occurred_at
    }
    INTERACTIONS {
        uuid id PK
        uuid ticket_id FK
        uuid counter_id FK "nullable"
        timestamptz started_at
        timestamptz ended_at
        string outcome
    }
    IDEMPOTENCY_KEYS {
        uuid id PK
        string key
        uuid tenant_id FK
        string request_hash "SHA-256 of body"
        uuid resource_id "nullable"
        jsonb response_json
        timestamptz expires_at
    }
    AUDIT_LOG {
        uuid id PK
        uuid tenant_id FK "nullable"
        uuid actor_user_id FK "nullable"
        string action
        string object_type
        string object_id
        jsonb before_json
        jsonb after_json
        timestamptz created_at
    }

    TENANTS ||--o{ LOCATIONS : "has"
    TENANTS ||--o{ SERVICES : "owns"
    TENANTS ||--o{ CHANNELS : "has"
    TENANTS ||--o{ USERS : "has"
    TENANTS ||--o{ ROLES : "has"
    LOCATIONS ||--o{ COUNTERS : "has"
    LOCATIONS ||--o{ TICKETS : "queues"
    SERVICES ||--o| LOCATIONS : "scoped to"
    SERVICES ||--o{ TICKETS : "categorizes"
    CHANNELS ||--o{ TICKETS : "source of"
    COUNTERS ||--o{ INTERACTIONS : "serves at"
    TICKETS ||--o{ TICKET_EVENTS : "logs"
    TICKETS ||--o{ INTERACTIONS : "has"
    USERS ||--o{ USER_ROLES : "assigned"
    ROLES ||--o{ USER_ROLES : "granted to"
```

## Index Rationale

### `tickets`

| Index | Columns | Rationale |
|-------|---------|-----------|
| `ix_tickets_location_status_created` | `(location_id, status, created_at)` | **Hot path for call-next and queue listing.** The call-next query filters by `location_id` + `status=WAITING` and orders by `priority, created_at`. This covering index prevents a sequential scan on the tickets table even as the table grows to millions of rows. |
| `ix_tickets_service_status_created` | `(service_id, status, created_at)` | Supports service-filtered queue queries common in multi-service locations. Without this, filtering by service would require scanning all tickets for the location. |
| `ix_tickets_tenant_id` | `tenant_id` | Multi-tenancy audit queries and cascade deletes. |
| `ix_tickets_number_location` | `(number, location_id)` | Used to look up a ticket by display number for quick desk lookup. |

### `ticket_events`

| Index | Columns | Rationale |
|-------|---------|-----------|
| `ix_ticket_events_ticket_occurred` | `(ticket_id, occurred_at)` | Every ticket detail page loads the full event history. This composite index enables O(log n) lookup and avoids sort operations on `occurred_at`. |

### `idempotency_keys`

| Index | Columns | Rationale |
|-------|---------|-----------|
| `ix_idempotency_tenant_key` | `(tenant_id, key)` | The idempotency check is on the hot path for every ticket creation request. Must be a fast unique lookup. |
| `ix_idempotency_expires_at` | `expires_at` | The cleanup job runs `DELETE WHERE expires_at < now()`. Without this index it would do a full table scan. |

### `interactions`

| Index | Columns | Rationale |
|-------|---------|-----------|
| `ix_interactions_counter_started` | `(counter_id, started_at)` | Analytics queries compute avg service time per counter over a date range. This supports range scans without a full table scan. |

## Constraints

| Constraint | Location | Reason |
|-----------|----------|--------|
| `ck_tickets_valid_status` | `tickets.status` | DB-level guard against invalid status strings — enforces state machine at the persistence layer too. |
| `ck_tickets_priority_range` | `tickets.priority` | Ensures priority is always 1–10. |
| `uq_idempotency_tenant_key` | `idempotency_keys` | Prevents two concurrent requests with the same key from both inserting. Combined with application-level locking. |
| `uq_users_tenant_email` | `users` | One email per tenant — prevents duplicate accounts. |
| `uq_roles_tenant_name` | `roles` | Prevents duplicate role names within a tenant. |

## Status State Machine

```
CREATED ──────────────────────────────────► CANCELED
   │
   ▼
WAITING ──────────────► CANCELED
   │                     NO_SHOW
   ▼
CALLED ────────────────► NO_SHOW
   │    └──────────────► CANCELED
   ▼                     WAITING (retry)
IN_SERVICE ────────────► COMPLETED
   │        └──────────► CANCELED
   │        └──────────► HOLD ──► WAITING
   └────────────────────► TRANSFERRED ──► WAITING
```

**Terminal states:** `COMPLETED`, `CANCELED`, `NO_SHOW` — no further transitions.

## Ticket Number Generation

The `number` field is a sequential integer scoped per location (not globally unique). The API uses:

```sql
SELECT COALESCE(MAX(number), 0) + 1 FROM tickets WHERE location_id = ?
```

This runs within the same transaction as the INSERT, making it safe under concurrent inserts. The human-readable form is `{service.prefix}-{number:04d}`, e.g. `G-0042`.
