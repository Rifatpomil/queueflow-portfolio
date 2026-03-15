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
    <div className="login-page">
      <div className="login-card">
        <h1 className="login-title">
          <span className="login-logo">◆</span> QueueFlow
        </h1>
        <p className="login-subtitle">
          AI-powered Queue Orchestration Platform
        </p>

        <form onSubmit={handleLogin} className="login-form">
          <div>
            <label className="login-label">DEV User</label>
            <select value={email} onChange={(e) => setEmail(e.target.value)}>
              {DEV_USERS.map((u) => (
                <option key={u.email} value={u.email}>
                  {u.label} – {u.email}
                </option>
              ))}
            </select>
          </div>
          {error && <div className="login-error">{error}</div>}
          <button type="submit" className="btn-primary login-btn" disabled={loading}>
            {loading ? "Signing in…" : "Sign in (DEV mode)"}
          </button>
        </form>

        <div className="login-dev-note">
          <strong>DEV mode:</strong> No password required. Kiosk: <a href="/kiosk">/kiosk</a> · Signage: <a href="/signage/00000000-0000-0000-0000-000000000020">/signage</a>
        </div>
      </div>
    </div>
  );
}
