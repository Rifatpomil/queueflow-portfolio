import { useEffect, useState } from "react";
import { adminApi, analyticsApi, aiApi } from "../api/client";
import { useAuth } from "../hooks/useAuth";
import type { Location, Counter, Service, KPISummary } from "../types";

const DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000010";
const DEMO_LOCATION_ID = "00000000-0000-0000-0000-000000000020";

export function AdminPanel() {
  const { user, hasRole } = useAuth();
  const [locations, setLocations] = useState<Location[]>([]);
  const [counters, setCounters] = useState<Counter[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [kpi, setKpi] = useState<KPISummary | null>(null);
  const [aiInsights, setAiInsights] = useState<{ insights: string[]; summary: string } | null>(null);
  const [tab, setTab] = useState<"overview" | "locations" | "services" | "counters">("overview");

  const tenantId = user?.tenant_id || DEMO_TENANT_ID;

  useEffect(() => {
    Promise.all([
      adminApi.listLocations(tenantId),
      adminApi.listServices(tenantId),
      adminApi.listCounters(DEMO_LOCATION_ID),
    ]).then(([l, s, c]) => {
      setLocations(l);
      setServices(s);
      setCounters(c);
    }).catch(() => {});

    const to = new Date().toISOString();
    const from = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    analyticsApi.summary(DEMO_LOCATION_ID, from, to)
      .then(setKpi)
      .catch(() => {});
    aiApi.insights(DEMO_LOCATION_ID, from, to)
      .then((r) => setAiInsights({ insights: r.insights, summary: r.summary }))
      .catch(() => {});
  }, [tenantId]);

  if (!hasRole("admin", "manager")) {
    return (
      <div style={{ color: "var(--danger)" }}>
        Access denied. Admin or Manager role required.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      <div>
        <h2>Admin Panel</h2>
        <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
          Tenant: {tenantId}
        </p>
      </div>

      {/* AI Insights */}
      {aiInsights && (
        <div className="card" style={{ borderLeft: "4px solid var(--primary)" }}>
          <h3 style={{ marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
            <span className="ai-badge">AI</span> Insights
          </h3>
          <ul style={{ margin: 0, paddingLeft: "20px", color: "var(--text-muted)", fontSize: "0.9rem", lineHeight: 1.8 }}>
            {aiInsights.insights.map((insight, i) => (
              <li key={i}>{insight}</li>
            ))}
          </ul>
        </div>
      )}

      {/* KPI Summary */}
      {kpi && (
        <div className="card">
          <h3 style={{ marginBottom: "12px" }}>Last 24h KPIs – Downtown Office</h3>
          <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
            {[
              { label: "Total Tickets", value: kpi.total_tickets },
              { label: "Completed", value: kpi.completed_tickets, color: "var(--success)" },
              { label: "Canceled", value: kpi.canceled_tickets, color: "var(--danger)" },
              { label: "No-Show", value: kpi.no_show_tickets, color: "var(--warning)" },
              {
                label: "Avg Wait",
                value: kpi.avg_wait_seconds
                  ? `${(kpi.avg_wait_seconds / 60).toFixed(1)}m`
                  : "—",
              },
              {
                label: "p95 Wait",
                value: kpi.p95_wait_seconds
                  ? `${(kpi.p95_wait_seconds / 60).toFixed(1)}m`
                  : "—",
              },
              { label: "Throughput/h", value: kpi.throughput_per_hour.toFixed(1) },
            ].map(({ label, value, color }) => (
              <div
                key={label}
                className="card"
                style={{ minWidth: "100px", textAlign: "center" }}
              >
                <div
                  style={{
                    fontSize: "1.5rem",
                    fontWeight: 700,
                    color: color ?? "var(--text)",
                  }}
                >
                  {value}
                </div>
                <div style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>{label}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid var(--border)", paddingBottom: "8px" }}>
        {(["overview", "locations", "services", "counters"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: tab === t ? "var(--primary)" : "var(--surface-2)",
              color: tab === t ? "#fff" : "var(--text-muted)",
              padding: "6px 14px",
              borderRadius: "var(--radius)",
              fontSize: "0.875rem",
              border: "none",
              cursor: "pointer",
              textTransform: "capitalize",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div style={{ display: "grid", gap: "12px", gridTemplateColumns: "repeat(3, 1fr)" }}>
          <div className="card" style={{ textAlign: "center" }}>
            <div style={{ fontSize: "2.5rem", fontWeight: 700, color: "var(--primary)" }}>
              {locations.length}
            </div>
            <div style={{ color: "var(--text-muted)" }}>Locations</div>
          </div>
          <div className="card" style={{ textAlign: "center" }}>
            <div style={{ fontSize: "2.5rem", fontWeight: 700, color: "var(--success)" }}>
              {services.length}
            </div>
            <div style={{ color: "var(--text-muted)" }}>Services</div>
          </div>
          <div className="card" style={{ textAlign: "center" }}>
            <div style={{ fontSize: "2.5rem", fontWeight: 700, color: "var(--warning)" }}>
              {counters.length}
            </div>
            <div style={{ color: "var(--text-muted)" }}>Counters</div>
          </div>
        </div>
      )}

      {tab === "locations" && (
        <ResourceTable
          title="Locations"
          columns={["Name", "Timezone", "Active"]}
          rows={locations.map((l) => [l.name, l.timezone, l.active ? "Yes" : "No"])}
        />
      )}
      {tab === "services" && (
        <ResourceTable
          title="Services"
          columns={["Name", "Prefix", "Category", "Active"]}
          rows={services.map((s) => [s.name, s.prefix, s.category ?? "—", s.active ? "Yes" : "No"])}
        />
      )}
      {tab === "counters" && (
        <ResourceTable
          title="Counters"
          columns={["Name", "Type", "Active"]}
          rows={counters.map((c) => [c.name, c.counter_type, c.active ? "Yes" : "No"])}
        />
      )}
    </div>
  );
}

function ResourceTable({
  title,
  columns,
  rows,
}: {
  title: string;
  columns: string[];
  rows: string[][];
}) {
  return (
    <div className="card">
      <h3 style={{ marginBottom: "12px" }}>{title}</h3>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col}
                style={{
                  textAlign: "left",
                  padding: "8px 12px",
                  color: "var(--text-muted)",
                  fontSize: "0.8rem",
                  borderBottom: "1px solid var(--border)",
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td
                  key={j}
                  style={{
                    padding: "10px 12px",
                    borderBottom: "1px solid var(--border)",
                    fontSize: "0.875rem",
                  }}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td
                colSpan={columns.length}
                style={{ padding: "16px 12px", color: "var(--text-muted)", textAlign: "center" }}
              >
                No records found
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
