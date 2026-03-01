import { useEffect, useState, useCallback } from "react";
import { ticketApi, adminApi, counterApi } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import { TicketCard } from "../components/TicketCard";
import { QueueStats } from "../components/QueueStats";
import type { Ticket, Location, Counter, Service } from "../types";

// Demo tenant/location IDs – in production these come from the user's JWT context
const DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000010";
const DEMO_LOCATION_ID = "00000000-0000-0000-0000-000000000020";

export function OperatorQueue() {
  const { user, hasRole } = useAuth();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [counters, setCounters] = useState<Counter[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [selectedCounter, setSelectedCounter] = useState<string>("");
  const [selectedService, setSelectedService] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("WAITING");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const tenantId = user?.tenant_id || DEMO_TENANT_ID;
  const locationId = DEMO_LOCATION_ID;

  const loadTickets = useCallback(async () => {
    try {
      const data = await ticketApi.list(locationId, {
        status: statusFilter || undefined,
        service_id: selectedService || undefined,
      });
      setTickets(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load tickets");
    }
  }, [locationId, statusFilter, selectedService]);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      adminApi.listCounters(locationId),
      adminApi.listServices(tenantId),
    ])
      .then(([c, s]) => {
        setCounters(c);
        setServices(s);
        if (c.length > 0) setSelectedCounter(c[0].id);
      })
      .catch(() => {/* ignore on demo */})
      .finally(() => setLoading(false));
  }, [locationId, tenantId]);

  useEffect(() => {
    loadTickets();
    // Poll every 10 seconds as a fallback
    const interval = setInterval(loadTickets, 10_000);
    return () => clearInterval(interval);
  }, [loadTickets]);

  const handleCallNext = async () => {
    if (!selectedCounter) return;
    try {
      const ticket = await counterApi.callNext(selectedCounter, selectedService || undefined);
      if (ticket) {
        setTickets((prev) => prev.map((t) => (t.id === ticket.id ? ticket : t)));
      } else {
        alert("Queue is empty");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Error calling next");
    }
  };

  const handleTicketUpdated = (updated: Ticket) => {
    setTickets((prev) => prev.map((t) => (t.id === updated.id ? updated : t)));
  };

  const waiting = tickets.filter((t) => t.status === "WAITING").length;
  const serving = tickets.filter((t) => t.status === "IN_SERVICE").length;
  const avgWait = null; // Would come from analytics endpoint

  if (loading) return <div style={{ color: "var(--text-muted)" }}>Loading…</div>;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h2 style={{ marginBottom: "4px" }}>Operator Queue</h2>
          <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
            Location: Downtown Office
          </p>
        </div>
        <a
          href={`/signage/${locationId}`}
          target="_blank"
          rel="noreferrer"
          style={{
            padding: "8px 16px",
            background: "var(--surface-2)",
            borderRadius: "var(--radius)",
            fontSize: "0.875rem",
          }}
        >
          Open Signage →
        </a>
      </div>

      <QueueStats waiting={waiting} serving={serving} avgWaitMinutes={avgWait} />

      {/* Controls */}
      <div className="card" style={{ display: "flex", gap: "12px", flexWrap: "wrap", alignItems: "flex-end" }}>
        <div>
          <label style={{ display: "block", marginBottom: "4px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Counter
          </label>
          <select
            value={selectedCounter}
            onChange={(e) => setSelectedCounter(e.target.value)}
            style={{ width: "auto" }}
          >
            {counters.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ display: "block", marginBottom: "4px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Service filter
          </label>
          <select
            value={selectedService}
            onChange={(e) => setSelectedService(e.target.value)}
            style={{ width: "auto" }}
          >
            <option value="">All services</option>
            {services.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label style={{ display: "block", marginBottom: "4px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Status
          </label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ width: "auto" }}
          >
            {["", "WAITING", "CALLED", "IN_SERVICE", "HOLD", "COMPLETED", "CANCELED"].map((s) => (
              <option key={s} value={s}>{s || "All"}</option>
            ))}
          </select>
        </div>
        {hasRole("admin", "manager", "staff") && (
          <button className="btn-primary" onClick={handleCallNext} disabled={!selectedCounter}>
            Call Next
          </button>
        )}
        <button className="btn-secondary" onClick={loadTickets}>Refresh</button>
      </div>

      {error && <div style={{ color: "var(--danger)" }}>{error}</div>}

      {/* Ticket list */}
      <div style={{ display: "grid", gap: "12px", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}>
        {tickets.length === 0 && (
          <div style={{ color: "var(--text-muted)" }}>No tickets found.</div>
        )}
        {tickets.map((t) => (
          <TicketCard
            key={t.id}
            ticket={t}
            onUpdated={handleTicketUpdated}
            counterId={selectedCounter || undefined}
          />
        ))}
      </div>
    </div>
  );
}
