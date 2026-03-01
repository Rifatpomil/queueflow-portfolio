# ADR 0002 – Ticket State Machine + Immutable Event Log

**Status:** Accepted
**Date:** 2024-01-01

## Context

Tickets go through a well-defined lifecycle: WAITING → CALLED → IN_SERVICE → COMPLETED, plus several exceptional paths (HOLD, TRANSFER, NO_SHOW, CANCELED).

The system needs to:
- Prevent invalid transitions (e.g., jumping from WAITING directly to COMPLETED)
- Provide a complete, auditable history of every ticket's lifecycle
- Support analytics (wait time = called_at − created_at)
- Be provably correct with unit tests

## Decision

Implement a **pure-function finite-state machine** (`app/state_machine/ticket_fsm.py`) with an **append-only event log** (`ticket_events` table).

### State machine design
- `VALID_TRANSITIONS: dict[str, set[str]]` — single source of truth for all allowed transitions
- `transition(current, target)` — pure function, raises `InvalidTransitionError` for illegal moves
- No database dependency; fully testable in isolation
- Every unit test runs in microseconds

### Event log design
- `ticket_events` is append-only; no UPDATE or DELETE ever touches it
- Every state transition writes an immutable `TicketEvent` row within the same transaction as the status update
- Payload stored as JSONB for flexibility (counter_id, transfer target, etc.)
- Timestamps are set by the application (not `server_default`) to avoid clock skew ambiguity

## Alternatives Considered

### A) Simple status field without event log
- **Pro:** Simpler schema
- **Con:** No audit trail; analytics must rely on computed columns that may be inconsistent; impossible to reconstruct "what happened" after the fact

### B) Event sourcing (pure event-driven, no status field)
- **Pro:** Perfect audit trail; event replay
- **Con:** Much higher complexity; requires event projections/snapshots; significant operational overhead; disproportionate for a queue system

### C) Triggers in the database to validate transitions
- **Pro:** Enforced at the DB level
- **Con:** Logic scattered between app and DB; harder to test; harder to reason about

## Chosen Approach Benefits

- State machine logic is in one small, testable file
- The `test_state_machine.py` exhaustively covers all (from, to) pairs
- Analytics computed directly from timestamps stored on the ticket row (`called_at`, `service_started_at`, `completed_at`) — no joins needed
- Full history available from `ticket_events` for audit purposes

## Consequences

- Adding a new state requires updating `VALID_TRANSITIONS` and the migration
- `ticket_events` table grows unboundedly; archival/partition strategy needed at scale (append `PARTITION BY RANGE (occurred_at)`)
- The event log is the source of truth for audit; the `status` column is a denormalized projection for performance
