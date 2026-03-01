"""
Ticket finite-state machine.

States
------
  CREATED → WAITING → CALLED → IN_SERVICE → COMPLETED
                                          ↘ HOLD → WAITING
                                          ↘ TRANSFERRED → WAITING
              ↓           ↓        ↓
           CANCELED   NO_SHOW   CANCELED

Design notes
-----------
- All valid transitions are declared in VALID_TRANSITIONS.
- ``transition()`` is a pure function; it raises ``InvalidTransitionError``
  for illegal moves so tests can verify every edge case without touching the DB.
- The event-type mapping ensures the correct ``TicketEvent`` is recorded
  alongside every state change.
"""
from __future__ import annotations

from app.models.ticket import TicketStatus
from app.models.ticket_event import EventType


class InvalidTransitionError(ValueError):
    """Raised when a state transition is not permitted."""

    def __init__(self, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Transition {from_status!r} → {to_status!r} is not allowed"
        )
        self.from_status = from_status
        self.to_status = to_status


# ---------------------------------------------------------------------------
# Allowed transitions: from_status → set of reachable to_statuses
# ---------------------------------------------------------------------------
VALID_TRANSITIONS: dict[str, set[str]] = {
    TicketStatus.CREATED: {
        TicketStatus.WAITING,
        TicketStatus.CANCELED,
    },
    TicketStatus.WAITING: {
        TicketStatus.CALLED,
        TicketStatus.CANCELED,
        TicketStatus.NO_SHOW,
    },
    TicketStatus.CALLED: {
        TicketStatus.IN_SERVICE,
        TicketStatus.WAITING,   # agent put them back (e.g. no show → retry)
        TicketStatus.NO_SHOW,
        TicketStatus.CANCELED,
    },
    TicketStatus.IN_SERVICE: {
        TicketStatus.COMPLETED,
        TicketStatus.HOLD,
        TicketStatus.TRANSFERRED,
        TicketStatus.CANCELED,
    },
    TicketStatus.HOLD: {
        TicketStatus.WAITING,
        TicketStatus.CANCELED,
    },
    TicketStatus.TRANSFERRED: {
        # Re-queued at new service/location
        TicketStatus.WAITING,
    },
    # Terminal states have no outgoing transitions
    TicketStatus.COMPLETED: set(),
    TicketStatus.CANCELED: set(),
    TicketStatus.NO_SHOW: set(),
}

# Map (from_status, to_status) → EventType to record
TRANSITION_EVENT: dict[tuple[str, str], str] = {
    (TicketStatus.CREATED, TicketStatus.WAITING): EventType.WAITING,
    (TicketStatus.WAITING, TicketStatus.CALLED): EventType.CALLED,
    (TicketStatus.CALLED, TicketStatus.IN_SERVICE): EventType.IN_SERVICE,
    (TicketStatus.CALLED, TicketStatus.WAITING): EventType.WAITING,
    (TicketStatus.IN_SERVICE, TicketStatus.COMPLETED): EventType.COMPLETED,
    (TicketStatus.IN_SERVICE, TicketStatus.HOLD): EventType.HOLD,
    (TicketStatus.IN_SERVICE, TicketStatus.TRANSFERRED): EventType.TRANSFERRED,
    (TicketStatus.HOLD, TicketStatus.WAITING): EventType.WAITING,
    (TicketStatus.TRANSFERRED, TicketStatus.WAITING): EventType.WAITING,
}
# All cancel/no-show transitions map to their respective event types
for _from in list(VALID_TRANSITIONS.keys()):
    if TicketStatus.CANCELED in VALID_TRANSITIONS[_from]:
        TRANSITION_EVENT[(_from, TicketStatus.CANCELED)] = EventType.CANCELED
    if TicketStatus.NO_SHOW in VALID_TRANSITIONS[_from]:
        TRANSITION_EVENT[(_from, TicketStatus.NO_SHOW)] = EventType.NO_SHOW


def transition(current: str, target: str) -> str:
    """
    Validate and return *target* status if the transition is legal.

    Raises
    ------
    InvalidTransitionError
        If the requested transition is not in VALID_TRANSITIONS.
    ValueError
        If *current* or *target* is not a known status string.
    """
    if current not in VALID_TRANSITIONS:
        raise ValueError(f"Unknown status: {current!r}")
    if target not in TicketStatus.ALL:
        raise ValueError(f"Unknown target status: {target!r}")
    if target not in VALID_TRANSITIONS[current]:
        raise InvalidTransitionError(current, target)
    return target


def event_type_for(from_status: str, to_status: str) -> str:
    """Return the EventType string for a given (from, to) transition."""
    key = (from_status, to_status)
    if key not in TRANSITION_EVENT:
        # Fallback: use the target status name as event type
        return to_status
    return TRANSITION_EVENT[key]


def is_terminal(status: str) -> bool:
    return status in TicketStatus.TERMINAL


def reachable_from(status: str) -> set[str]:
    """Return the set of statuses reachable from *status*."""
    return VALID_TRANSITIONS.get(status, set())
