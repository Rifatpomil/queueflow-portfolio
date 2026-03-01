# ADR 0001 – Storage Strategy: PostgreSQL + Redis + Celery

**Status:** Accepted
**Date:** 2024-01-01

## Context

The system needs:
1. Strongly-consistent storage for tickets (ACID transactions, especially for call-next)
2. A pub/sub mechanism to fan out signage updates to connected SSE clients
3. A background job system for KPI rollups and cleanup

Several alternatives were considered.

## Decision

Use **PostgreSQL 15** as the primary data store, **Redis 7** as the pub/sub and cache layer, and **Celery + Redis** as the background job system.

## Alternatives Considered

### A) PostgreSQL + Redis + Celery (chosen)
- **Pro:** Industry standard, well-understood operational model
- **Pro:** PostgreSQL's `SELECT FOR UPDATE SKIP LOCKED` is purpose-built for queue operations
- **Pro:** JSONB for flexible payloads (ticket_events, audit_log) without schema churn
- **Pro:** Redis pub/sub is a perfect fit for fan-out to N signage screens
- **Con:** Two distinct datastores to operate

### B) PostgreSQL alone (LISTEN/NOTIFY)
- **Pro:** Single datastore
- **Con:** LISTEN/NOTIFY has no fan-out to many clients; no backpressure; no message history
- **Con:** No rate limiting or caching primitive built in

### C) MongoDB + Redis
- **Pro:** Flexible schema
- **Con:** Weaker consistency guarantees; `SELECT FOR UPDATE` equivalent is complex; no native transactions across collections until 4.0 multi-doc

### D) SQLite (for simplicity)
- Ruled out immediately: no `SELECT FOR UPDATE SKIP LOCKED`, no concurrent writers

## Consequences

- We depend on two external services in production (Postgres, Redis)
- Docker Compose makes local setup trivial
- The Celery+Redis combo means the broker doubles as the pub/sub bus — reducing total infrastructure footprint
- Tests use SQLite for unit tests (state machine tests only) and real Postgres for integration tests
