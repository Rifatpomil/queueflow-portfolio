# Architecture

## Overview

QueueFlow is a multi-tenant, multi-location queue orchestration platform.
The system is designed for high reliability and real-time signage updates
with a clean separation of concerns at every layer.

## High-Level Component Diagram

```mermaid
graph TB
    Browser["Browser\n(React + Vite)"]
    Nginx["Nginx\n(Reverse Proxy)"]
    API["FastAPI\n(Uvicorn)"]
    Worker["Celery Worker\n(Background jobs)"]
    Beat["Celery Beat\n(Scheduler)"]
    DB[("PostgreSQL 15\n(Primary data store)")]
    Redis[("Redis 7\n(Pub/Sub + Cache + Broker)")]
    KC["Keycloak 23\n(OIDC / SSO)"]

    Browser -->|HTTP + SSE| Nginx
    Nginx -->|Proxy| API
    Browser -->|OIDC (optional)| KC
    API -->|SQL (asyncpg)| DB
    API -->|Pub/Sub + Cache| Redis
    API -->|JWT validation| KC
    Worker -->|SQL (psycopg2)| DB
    Worker -->|Task results| Redis
    Beat -->|Enqueue tasks| Redis
    Redis -->|Tasks| Worker
```

## Request Flow – Create Ticket

```mermaid
sequenceDiagram
    participant C as Client
    participant A as API (FastAPI)
    participant D as PostgreSQL
    participant R as Redis
    participant SSE as Signage SSE clients

    C->>A: POST /v1/tickets + Idempotency-Key
    A->>D: Check idempotency_keys table
    alt Key exists
        D-->>A: Return cached resource_id
        A-->>C: 200 (replay)
    else New request
        A->>D: BEGIN TRANSACTION
        A->>D: SELECT MAX(number) + 1 WHERE location_id=X
        A->>D: INSERT INTO tickets (status=WAITING)
        A->>D: INSERT INTO ticket_events (type=CREATED)
        A->>D: INSERT INTO idempotency_keys
        A->>D: COMMIT
        A->>R: PUBLISH signage:{location_id}
        R-->>SSE: Push update
        A-->>C: 201 Created
    end
```

## Request Flow – Call Next (Concurrency-Safe)

```mermaid
sequenceDiagram
    participant O1 as Operator 1
    participant O2 as Operator 2
    participant A as API
    participant D as PostgreSQL

    O1->>A: POST /v1/counters/C1/call-next
    O2->>A: POST /v1/counters/C2/call-next
    Note over A,D: Both requests arrive simultaneously

    A->>D: BEGIN (O1)
    A->>D: BEGIN (O2)

    D->>D: SELECT id FROM tickets WHERE status=WAITING\nORDER BY priority,created_at LIMIT 1\nFOR UPDATE SKIP LOCKED (O1)
    Note over D: O1 locks ticket T-0001

    D->>D: SELECT id FROM tickets WHERE status=WAITING\nORDER BY priority,created_at LIMIT 1\nFOR UPDATE SKIP LOCKED (O2)
    Note over D: O2 sees T-0001 locked → gets T-0002

    D-->>A: T-0001 (O1)
    A->>D: UPDATE tickets SET status=CALLED (T-0001)
    A->>D: COMMIT (O1)

    D-->>A: T-0002 (O2)
    A->>D: UPDATE tickets SET status=CALLED (T-0002)
    A->>D: COMMIT (O2)

    Note over O1,O2: Each operator gets a different ticket ✓
```

## Layered Architecture

```
┌──────────────────────────────────────┐
│  HTTP Routers  (app/api/v1/)         │  Input validation, auth checks
├──────────────────────────────────────┤
│  Services      (app/services/)       │  Business rules, RBAC, orchestration
├──────────────────────────────────────┤
│  Repositories  (app/repositories/)   │  DB queries, no business logic
├──────────────────────────────────────┤
│  Models        (app/models/)         │  SQLAlchemy ORM, indexes, constraints
├──────────────────────────────────────┤
│  PostgreSQL 15 + Redis 7             │  Persistence + pub/sub + cache
└──────────────────────────────────────┘
```

## Signage Real-Time Flow

```mermaid
graph LR
    A[Ticket state change] -->|publish| R[Redis\nsignage:location_id]
    R -->|subscribe| SSE1[SSE Handler 1]
    R -->|subscribe| SSE2[SSE Handler 2]
    SSE1 -->|text/event-stream| Board1[Signage Board 1]
    SSE2 -->|text/event-stream| Board2[Signage Board 2]
```

Each SSE handler:
1. Subscribes to `signage:{location_id}` on Redis
2. Sends an initial snapshot immediately
3. Re-fetches + pushes a new snapshot on every Redis message
4. Sends a heartbeat comment every 30s to keep proxy connections alive

## Multi-Tenancy

Every major entity (location, service, counter, ticket, user) has a `tenant_id`
foreign key. The service layer enforces that actors can only operate on resources
belonging to their own tenant. There is no cross-tenant query at any layer.

## Background Jobs (Celery)

| Task | Schedule | Queue |
|------|----------|-------|
| `kpi_rollup` | Every hour (+5 min) | analytics |
| `cleanup_idempotency_keys` | Daily 02:00 UTC | default |
| `auto_no_show_called_tickets` | Every 10 minutes | default |
