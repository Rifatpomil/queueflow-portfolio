import type { Ticket } from "../types";
import { ticketApi, counterApi } from "../api/client";
import { useState } from "react";

const STATUS_BADGE: Record<string, string> = {
  WAITING: "badge-waiting",
  CALLED: "badge-called",
  IN_SERVICE: "badge-inservice",
  COMPLETED: "badge-completed",
  CANCELED: "badge-canceled",
  HOLD: "badge-hold",
  NO_SHOW: "badge-canceled",
  TRANSFERRED: "badge-hold",
  CREATED: "badge-waiting",
};

interface Props {
  ticket: Ticket;
  onUpdated: (t: Ticket) => void;
  counterId?: string;
}

export function TicketCard({ ticket, onUpdated, counterId }: Props) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const act = async (fn: () => Promise<Ticket | null>) => {
    setLoading(true);
    setErr(null);
    try {
      const updated = await fn();
      if (updated) onUpdated(updated);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  };

  const canCall = ticket.status === "WAITING" && counterId;
  const canStartService = ticket.status === "CALLED";
  const canComplete = ticket.status === "IN_SERVICE";
  const canHold = ticket.status === "IN_SERVICE";
  const canCancel = !["COMPLETED", "CANCELED", "NO_SHOW"].includes(ticket.status);
  const canNoShow = ticket.status === "CALLED";

  return (
    <div
      className="card"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "8px",
        borderLeft: "4px solid var(--primary)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontWeight: 700, fontSize: "1.25rem" }}>{ticket.display_number}</span>
        <span className={`badge ${STATUS_BADGE[ticket.status] ?? ""}`}>{ticket.status}</span>
      </div>
      <div style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
        Priority {ticket.priority} · #{ticket.number}
        {ticket.notes && <> · {ticket.notes}</>}
      </div>
      {err && <div style={{ color: "var(--danger)", fontSize: "0.8rem" }}>{err}</div>}
      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
        {canCall && counterId && (
          <button
            className="btn-primary"
            disabled={loading}
            onClick={() => act(() => counterApi.callNext(counterId))}
          >
            Call
          </button>
        )}
        {canStartService && (
          <button
            className="btn-success"
            disabled={loading}
            onClick={() => act(() => ticketApi.startService(ticket.id))}
          >
            Start
          </button>
        )}
        {canComplete && (
          <button
            className="btn-success"
            disabled={loading}
            onClick={() => act(() => ticketApi.complete(ticket.id))}
          >
            Complete
          </button>
        )}
        {canHold && (
          <button
            className="btn-secondary"
            disabled={loading}
            onClick={() => act(() => ticketApi.hold(ticket.id))}
          >
            Hold
          </button>
        )}
        {canNoShow && (
          <button
            className="btn-secondary"
            disabled={loading}
            onClick={() => act(() => ticketApi.noShow(ticket.id))}
          >
            No Show
          </button>
        )}
        {canCancel && (
          <button
            className="btn-danger"
            disabled={loading}
            onClick={() => act(() => ticketApi.cancel(ticket.id))}
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  );
}
