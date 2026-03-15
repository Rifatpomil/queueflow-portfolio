/**
 * Typed API client – wraps fetch with auth headers, error handling, and
 * base URL configuration.
 */

const BASE_URL = import.meta.env.VITE_API_URL || "";

function getToken(): string | null {
  return localStorage.getItem("access_token");
}

export function setToken(token: string): void {
  localStorage.setItem("access_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("access_token");
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  extraHeaders?: Record<string, string>
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...extraHeaders,
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const resp = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (resp.status === 204) return undefined as T;

  const data = await resp.json().catch(() => ({ detail: resp.statusText }));

  if (!resp.ok) {
    const message = data?.detail ?? `HTTP ${resp.status}`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }

  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown, headers?: Record<string, string>) =>
    request<T>("POST", path, body, headers),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

// ── Auth ──────────────────────────────────────────────────────────────────────
export const authApi = {
  devLogin: (email: string) =>
    api.post<{ access_token: string; token_type: string; expires_in: number }>(
      "/dev/login",
      { email }
    ),
};

// ── Tickets ────────────────────────────────────────────────────────────────────
import type { Ticket } from "../types";

export const ticketApi = {
  list: (locationId: string, params?: { status?: string; service_id?: string }) => {
    const qs = new URLSearchParams({ location_id: locationId, ...(params || {}) });
    return api.get<Ticket[]>(`/v1/tickets?${qs}`);
  },
  create: (body: { location_id: string; service_id?: string; priority?: number }, idempotencyKey?: string) =>
    api.post<Ticket>("/v1/tickets", body, idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined),
  cancel: (id: string) => api.post<Ticket>(`/v1/tickets/${id}/cancel`),
  hold: (id: string) => api.post<Ticket>(`/v1/tickets/${id}/hold`),
  startService: (id: string) => api.post<Ticket>(`/v1/tickets/${id}/start-service`),
  complete: (id: string) => api.post<Ticket>(`/v1/tickets/${id}/complete`),
  noShow: (id: string) => api.post<Ticket>(`/v1/tickets/${id}/no-show`),
};

// ── Counters ──────────────────────────────────────────────────────────────────
export const counterApi = {
  callNext: (counterId: string, serviceId?: string) =>
    api.post<Ticket | null>(`/v1/counters/${counterId}/call-next`, { service_id: serviceId }),
};

// ── Signage ───────────────────────────────────────────────────────────────────
import type { SignageSnapshot } from "../types";

export const signageApi = {
  snapshot: (locationId: string) =>
    api.get<SignageSnapshot>(`/v1/signage/${locationId}`),
};

// ── Admin ─────────────────────────────────────────────────────────────────────
import type { Location, Service, Counter } from "../types";

export const adminApi = {
  listLocations: (tenantId: string) =>
    api.get<Location[]>(`/v1/admin/locations?tenant_id=${tenantId}`),
  listServices: (tenantId: string) =>
    api.get<Service[]>(`/v1/admin/services?tenant_id=${tenantId}`),
  listCounters: (locationId: string) =>
    api.get<Counter[]>(`/v1/admin/counters?location_id=${locationId}`),
};

// ── Analytics ─────────────────────────────────────────────────────────────────
import type { KPISummary } from "../types";

export const analyticsApi = {
  summary: (locationId: string, from: string, to: string) =>
    api.get<KPISummary>(`/v1/analytics/location/${locationId}/summary?from=${from}&to=${to}`),
};

// ── AI ───────────────────────────────────────────────────────────────────────
export interface ServiceSuggestion {
  suggested_service_id: string | null;
  suggested_service_name: string | null;
  confidence: number;
}

export interface WaitPrediction {
  predicted_wait_minutes: number;
  waiting_count: number;
  confidence: number;
}

export interface AIInsights {
  insights: string[];
  kpi: KPISummary & Record<string, unknown>;
  summary: string;
}

export const aiApi = {
  suggestService: (tenantId: string, locationId: string, query: string) =>
    api.post<ServiceSuggestion>(
      "/v1/ai/suggest-service",
      { tenant_id: tenantId, location_id: locationId, query }
    ),
  kioskSuggestService: (locationId: string, query: string) =>
    api.post<ServiceSuggestion>("/v1/ai/kiosk/suggest-service", {
      location_id: locationId,
      query,
    }),
  predictWait: (locationId: string) =>
    api.get<WaitPrediction>(`/v1/ai/predict-wait?location_id=${locationId}`),
  insights: (locationId: string, from: string, to: string) =>
    api.get<AIInsights>(`/v1/ai/insights/${locationId}?from=${from}&to=${to}`),
};

// ── Kiosk (public, no auth) ───────────────────────────────────────────────────
export const kioskApi = {
  createTicket: (body: { location_id: string; service_id: string }, idempotencyKey: string) =>
    api.post<Ticket>("/v1/kiosk/tickets", body, {
      "Idempotency-Key": idempotencyKey,
    }),
};
