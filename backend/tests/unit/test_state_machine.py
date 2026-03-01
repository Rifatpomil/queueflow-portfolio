"""Unit tests for the ticket finite-state machine.

These tests are pure Python – no database, no network, fast.
They document every valid and invalid transition.
"""
import pytest

from app.models.ticket import TicketStatus
from app.state_machine.ticket_fsm import (
    VALID_TRANSITIONS,
    InvalidTransitionError,
    event_type_for,
    is_terminal,
    reachable_from,
    transition,
)


class TestValidTransitions:
    def test_created_to_waiting(self):
        assert transition(TicketStatus.CREATED, TicketStatus.WAITING) == TicketStatus.WAITING

    def test_created_to_canceled(self):
        assert transition(TicketStatus.CREATED, TicketStatus.CANCELED) == TicketStatus.CANCELED

    def test_waiting_to_called(self):
        assert transition(TicketStatus.WAITING, TicketStatus.CALLED) == TicketStatus.CALLED

    def test_waiting_to_canceled(self):
        assert transition(TicketStatus.WAITING, TicketStatus.CANCELED) == TicketStatus.CANCELED

    def test_waiting_to_no_show(self):
        assert transition(TicketStatus.WAITING, TicketStatus.NO_SHOW) == TicketStatus.NO_SHOW

    def test_called_to_in_service(self):
        assert transition(TicketStatus.CALLED, TicketStatus.IN_SERVICE) == TicketStatus.IN_SERVICE

    def test_called_to_waiting_retry(self):
        """An agent can put a CALLED ticket back to WAITING for retry."""
        assert transition(TicketStatus.CALLED, TicketStatus.WAITING) == TicketStatus.WAITING

    def test_called_to_no_show(self):
        assert transition(TicketStatus.CALLED, TicketStatus.NO_SHOW) == TicketStatus.NO_SHOW

    def test_called_to_canceled(self):
        assert transition(TicketStatus.CALLED, TicketStatus.CANCELED) == TicketStatus.CANCELED

    def test_in_service_to_completed(self):
        assert transition(TicketStatus.IN_SERVICE, TicketStatus.COMPLETED) == TicketStatus.COMPLETED

    def test_in_service_to_hold(self):
        assert transition(TicketStatus.IN_SERVICE, TicketStatus.HOLD) == TicketStatus.HOLD

    def test_in_service_to_transferred(self):
        assert transition(TicketStatus.IN_SERVICE, TicketStatus.TRANSFERRED) == TicketStatus.TRANSFERRED

    def test_in_service_to_canceled(self):
        assert transition(TicketStatus.IN_SERVICE, TicketStatus.CANCELED) == TicketStatus.CANCELED

    def test_hold_to_waiting(self):
        assert transition(TicketStatus.HOLD, TicketStatus.WAITING) == TicketStatus.WAITING

    def test_hold_to_canceled(self):
        assert transition(TicketStatus.HOLD, TicketStatus.CANCELED) == TicketStatus.CANCELED

    def test_transferred_to_waiting(self):
        assert transition(TicketStatus.TRANSFERRED, TicketStatus.WAITING) == TicketStatus.WAITING


class TestInvalidTransitions:
    def test_waiting_to_in_service_skips_called(self):
        with pytest.raises(InvalidTransitionError) as exc_info:
            transition(TicketStatus.WAITING, TicketStatus.IN_SERVICE)
        assert "WAITING" in str(exc_info.value)
        assert "IN_SERVICE" in str(exc_info.value)

    def test_waiting_to_completed_invalid(self):
        with pytest.raises(InvalidTransitionError):
            transition(TicketStatus.WAITING, TicketStatus.COMPLETED)

    def test_completed_is_terminal_no_transitions(self):
        for target in TicketStatus.ALL - {TicketStatus.COMPLETED}:
            with pytest.raises(InvalidTransitionError):
                transition(TicketStatus.COMPLETED, target)

    def test_canceled_is_terminal(self):
        for target in TicketStatus.ALL - {TicketStatus.CANCELED}:
            with pytest.raises(InvalidTransitionError):
                transition(TicketStatus.CANCELED, target)

    def test_no_show_is_terminal(self):
        for target in TicketStatus.ALL - {TicketStatus.NO_SHOW}:
            with pytest.raises(InvalidTransitionError):
                transition(TicketStatus.NO_SHOW, target)

    def test_in_service_to_waiting_invalid(self):
        with pytest.raises(InvalidTransitionError):
            transition(TicketStatus.IN_SERVICE, TicketStatus.WAITING)

    def test_created_to_in_service_skips_states(self):
        with pytest.raises(InvalidTransitionError):
            transition(TicketStatus.CREATED, TicketStatus.IN_SERVICE)

    def test_unknown_source_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown status"):
            transition("INVALID_STATUS", TicketStatus.WAITING)

    def test_unknown_target_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown target status"):
            transition(TicketStatus.WAITING, "INVALID_TARGET")


class TestInvalidTransitionError:
    def test_error_has_from_to_attributes(self):
        exc = InvalidTransitionError(TicketStatus.WAITING, TicketStatus.COMPLETED)
        assert exc.from_status == TicketStatus.WAITING
        assert exc.to_status == TicketStatus.COMPLETED

    def test_error_message_readable(self):
        exc = InvalidTransitionError("WAITING", "COMPLETED")
        assert "WAITING" in str(exc)
        assert "COMPLETED" in str(exc)


class TestHelpers:
    def test_is_terminal_completed(self):
        assert is_terminal(TicketStatus.COMPLETED) is True

    def test_is_terminal_canceled(self):
        assert is_terminal(TicketStatus.CANCELED) is True

    def test_is_terminal_no_show(self):
        assert is_terminal(TicketStatus.NO_SHOW) is True

    def test_is_not_terminal_waiting(self):
        assert is_terminal(TicketStatus.WAITING) is False

    def test_is_not_terminal_in_service(self):
        assert is_terminal(TicketStatus.IN_SERVICE) is False

    def test_reachable_from_waiting(self):
        reachable = reachable_from(TicketStatus.WAITING)
        assert TicketStatus.CALLED in reachable
        assert TicketStatus.CANCELED in reachable
        assert TicketStatus.IN_SERVICE not in reachable

    def test_reachable_from_terminal_empty(self):
        for terminal in TicketStatus.TERMINAL:
            assert reachable_from(terminal) == set()

    def test_event_type_for_called(self):
        from app.models.ticket_event import EventType
        assert event_type_for(TicketStatus.WAITING, TicketStatus.CALLED) == EventType.CALLED

    def test_event_type_for_completed(self):
        from app.models.ticket_event import EventType
        result = event_type_for(TicketStatus.IN_SERVICE, TicketStatus.COMPLETED)
        assert result == EventType.COMPLETED


class TestTransitionMatrix:
    """Exhaustively verify the complete transition matrix."""

    def test_all_declared_transitions_pass(self):
        """Every (from, to) pair in VALID_TRANSITIONS must succeed."""
        for from_status, targets in VALID_TRANSITIONS.items():
            for to_status in targets:
                result = transition(from_status, to_status)
                assert result == to_status

    def test_undeclared_transitions_all_raise(self):
        """Every (from, to) pair NOT in VALID_TRANSITIONS must raise."""
        all_statuses = TicketStatus.ALL
        for from_status in all_statuses:
            valid_targets = VALID_TRANSITIONS.get(from_status, set())
            invalid_targets = all_statuses - valid_targets - {from_status}
            for to_status in invalid_targets:
                with pytest.raises((InvalidTransitionError, ValueError)):
                    transition(from_status, to_status)
