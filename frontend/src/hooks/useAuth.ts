/**
 * useAuth – reads the current JWT from localStorage and decodes the payload.
 */
import { useEffect, useState } from "react";
import { clearToken } from "../api/client";
import type { AuthUser } from "../types";

function parseJwt(token: string): AuthUser | null {
  try {
    const [, payload] = token.split(".");
    const decoded = JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
    return {
      sub: decoded.sub,
      email: decoded.email ?? decoded.preferred_username ?? "",
      display_name: decoded.display_name ?? decoded.name ?? decoded.email ?? "",
      tenant_id: decoded.tenant_id ?? "",
      roles: decoded.roles ?? decoded.realm_access?.roles ?? [],
    };
  } catch {
    return null;
  }
}

export function useAuth() {
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (token) {
      const parsed = parseJwt(token);
      // Check expiry
      if (parsed) {
        try {
          const [, payload] = token.split(".");
          const { exp } = JSON.parse(atob(payload));
          if (exp && Date.now() / 1000 > exp) {
            clearToken();
            setUser(null);
            return;
          }
        } catch {
          /* ignore */
        }
        setUser(parsed);
      }
    }
  }, []);

  const logout = () => {
    clearToken();
    setUser(null);
  };

  const hasRole = (...roles: string[]) =>
    user?.roles.some((r) => roles.includes(r)) ?? false;

  return { user, logout, hasRole };
}
