import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <nav
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "12px 24px",
        background: "var(--surface)",
        borderBottom: "1px solid var(--border)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "24px" }}>
        <span style={{ fontWeight: 700, fontSize: "1.1rem", color: "var(--primary)" }}>
          QueueFlow
        </span>
        <Link to="/">Queue</Link>
        <Link to="/admin">Admin</Link>
      </div>
      {user && (
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <span style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
            {user.display_name} ({user.roles.join(", ")})
          </span>
          <button className="btn-secondary" onClick={handleLogout}>
            Logout
          </button>
        </div>
      )}
    </nav>
  );
}
