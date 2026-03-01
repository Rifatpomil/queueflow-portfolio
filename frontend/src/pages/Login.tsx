import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { authApi, setToken } from "../api/client";

const DEV_USERS = [
  { email: "admin@queueflow.dev", label: "Admin" },
  { email: "manager@queueflow.dev", label: "Manager" },
  { email: "staff@queueflow.dev", label: "Staff" },
  { email: "viewer@queueflow.dev", label: "Viewer (Signage)" },
];

export function Login() {
  const [email, setEmail] = useState("staff@queueflow.dev");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const resp = await authApi.devLogin(email);
      setToken(resp.access_token);
      navigate("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
      }}
    >
      <div className="card" style={{ width: "100%", maxWidth: "400px" }}>
        <h1 style={{ marginBottom: "8px", color: "var(--primary)" }}>QueueFlow</h1>
        <p style={{ color: "var(--text-muted)", marginBottom: "24px", fontSize: "0.9rem" }}>
          Multi-site Queue Orchestration Platform
        </p>

        <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          <div>
            <label style={{ display: "block", marginBottom: "6px", fontSize: "0.875rem" }}>
              DEV User
            </label>
            <select value={email} onChange={(e) => setEmail(e.target.value)}>
              {DEV_USERS.map((u) => (
                <option key={u.email} value={u.email}>
                  {u.label} – {u.email}
                </option>
              ))}
            </select>
          </div>
          {error && <div style={{ color: "var(--danger)", fontSize: "0.875rem" }}>{error}</div>}
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? "Signing in…" : "Sign in (DEV mode)"}
          </button>
        </form>

        <div style={{ marginTop: "16px", padding: "12px", background: "var(--surface-2)", borderRadius: "var(--radius)", fontSize: "0.8rem", color: "var(--text-muted)" }}>
          <strong>DEV mode:</strong> No password required. Select a role and sign in.
          For Signage display: <code>/signage/&lt;location_id&gt;</code> (no auth).
        </div>
      </div>
    </div>
  );
}
