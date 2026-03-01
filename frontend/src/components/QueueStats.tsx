interface Props {
  waiting: number;
  avgWaitMinutes: number | null;
  serving: number;
}

export function QueueStats({ waiting, avgWaitMinutes, serving }: Props) {
  return (
    <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
      {[
        { label: "Waiting", value: waiting, color: "var(--primary)" },
        { label: "Now Serving", value: serving, color: "var(--success)" },
        {
          label: "Avg Wait",
          value: avgWaitMinutes !== null ? `${avgWaitMinutes}m` : "—",
          color: "var(--warning)",
        },
      ].map(({ label, value, color }) => (
        <div
          key={label}
          className="card"
          style={{ minWidth: "120px", textAlign: "center", borderTop: `3px solid ${color}` }}
        >
          <div style={{ fontSize: "2rem", fontWeight: 700, color }}>{value}</div>
          <div style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>{label}</div>
        </div>
      ))}
    </div>
  );
}
