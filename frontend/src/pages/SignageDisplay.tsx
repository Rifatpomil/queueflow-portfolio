/**
 * SignageDisplay – public fullscreen board that auto-updates via SSE.
 *
 * Navigate to /signage/<location_id> — no login required.
 */
import { useParams } from "react-router-dom";
import { useSignage } from "../hooks/useSignage";

export function SignageDisplay() {
  const { locationId } = useParams<{ locationId: string }>();
  const { snapshot, error, connected } = useSignage(locationId ?? null);

  if (!locationId) return <div className="signage-error">No location ID provided.</div>;

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#050a14",
        color: "#f1f5f9",
        padding: "32px",
        fontFamily: "'Inter', system-ui, sans-serif",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "32px",
          borderBottom: "2px solid #1e3a5f",
          paddingBottom: "16px",
        }}
      >
        <div>
          <div style={{ fontSize: "2rem", fontWeight: 800, color: "#3b82f6" }}>
            {snapshot?.location_name ?? "QueueFlow"}
          </div>
          <div style={{ color: "#64748b", fontSize: "0.875rem" }}>
            Queue Display Board
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "0.75rem",
              color: connected ? "#4ade80" : "#f87171",
            }}
          >
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: "currentColor",
                display: "inline-block",
              }}
            />
            {connected ? "Live" : "Reconnecting…"}
          </div>
          {snapshot && (
            <div style={{ color: "#475569", fontSize: "0.7rem" }}>
              {new Date(snapshot.snapshot_at).toLocaleTimeString()}
            </div>
          )}
        </div>
      </div>

      {error && (
        <div style={{ color: "#f87171", marginBottom: "16px" }}>{error}</div>
      )}

      {snapshot ? (
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "32px" }}>
          {/* Now Serving */}
          <div>
            <h2
              style={{
                color: "#94a3b8",
                fontSize: "0.875rem",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                marginBottom: "16px",
              }}
            >
              Now Serving
            </h2>
            {snapshot.now_serving.length === 0 ? (
              <div style={{ color: "#475569", fontSize: "1.5rem" }}>—</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {snapshot.now_serving.map((entry) => (
                  <div
                    key={entry.id}
                    style={{
                      background: "#0f2027",
                      border: "2px solid #22c55e",
                      borderRadius: "12px",
                      padding: "20px 24px",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <span
                      style={{
                        fontSize: "3.5rem",
                        fontWeight: 900,
                        color: "#22c55e",
                        letterSpacing: "-0.02em",
                        fontVariantNumeric: "tabular-nums",
                      }}
                    >
                      {entry.display_number}
                    </span>
                    <div style={{ textAlign: "right" }}>
                      {entry.counter_name && (
                        <div style={{ fontSize: "1.25rem", color: "#f1f5f9" }}>
                          {entry.counter_name}
                        </div>
                      )}
                      {entry.service_name && (
                        <div style={{ fontSize: "0.875rem", color: "#64748b" }}>
                          {entry.service_name}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Stats + Recently Called */}
          <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            {/* Stats */}
            <div
              style={{
                background: "#0f172a",
                border: "1px solid #1e293b",
                borderRadius: "12px",
                padding: "20px",
              }}
            >
              <div style={{ marginBottom: "12px" }}>
                <div
                  style={{
                    fontSize: "4rem",
                    fontWeight: 900,
                    color: "#3b82f6",
                    lineHeight: 1,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {snapshot.waiting_count}
                </div>
                <div style={{ color: "#64748b", fontSize: "0.875rem" }}>Waiting</div>
              </div>
              {snapshot.avg_wait_minutes !== null && (
                <div>
                  <div style={{ fontSize: "2rem", fontWeight: 700, color: "#f59e0b" }}>
                    ~{snapshot.avg_wait_minutes}m
                  </div>
                  <div style={{ color: "#64748b", fontSize: "0.875rem" }}>Avg wait</div>
                </div>
              )}
            </div>

            {/* Recently Called */}
            {snapshot.recently_called.length > 0 && (
              <div>
                <h2
                  style={{
                    color: "#94a3b8",
                    fontSize: "0.75rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.1em",
                    marginBottom: "8px",
                  }}
                >
                  Recently Called
                </h2>
                <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                  {snapshot.recently_called.slice(0, 8).map((entry) => (
                    <div
                      key={entry.id}
                      style={{
                        background: "#0f172a",
                        border: "1px solid #1e3a5f",
                        borderRadius: "8px",
                        padding: "8px 16px",
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <span
                        style={{
                          fontWeight: 700,
                          fontSize: "1.25rem",
                          color: "#93c5fd",
                          fontVariantNumeric: "tabular-nums",
                        }}
                      >
                        {entry.display_number}
                      </span>
                      {entry.counter_name && (
                        <span style={{ color: "#64748b", fontSize: "0.8rem" }}>
                          {entry.counter_name}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div style={{ color: "#475569", fontSize: "1.5rem", textAlign: "center", marginTop: "80px" }}>
          Connecting to queue…
        </div>
      )}
    </div>
  );
}
