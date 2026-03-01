// ── Core domain types matching backend Pydantic schemas ─────────────────────

export type TicketStatus =
  | "CREATED"
  | "WAITING"
  | "CALLED"
  | "IN_SERVICE"
  | "HOLD"
  | "TRANSFERRED"
  | "COMPLETED"
  | "CANCELED"
  | "NO_SHOW";

export interface Ticket {
  id: string;
  tenant_id: string;
  location_id: string;
  service_id: string | null;
  channel_id: string | null;
  assigned_counter_id: string | null;
  number: number;
  display_number: string;
  status: TicketStatus;
  priority: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
  called_at: string | null;
  service_started_at: string | null;
  completed_at: string | null;
}

export interface SignageTicketEntry {
  id: string;
  display_number: string;
  status: TicketStatus;
  counter_name: string | null;
  service_name: string | null;
  called_at: string | null;
}

export interface SignageSnapshot {
  location_id: string;
  location_name: string;
  now_serving: SignageTicketEntry[];
  recently_called: SignageTicketEntry[];
  waiting_count: number;
  avg_wait_minutes: number | null;
  snapshot_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Location {
  id: string;
  tenant_id: string;
  name: string;
  address: string | null;
  timezone: string;
  active: boolean;
  created_at: string;
}

export interface Service {
  id: string;
  tenant_id: string;
  location_id: string | null;
  name: string;
  prefix: string;
  category: string | null;
  active: boolean;
  avg_service_minutes: number;
  created_at: string;
}

export interface Counter {
  id: string;
  location_id: string;
  name: string;
  counter_type: string;
  active: boolean;
  created_at: string;
}

export interface KPISummary {
  location_id: string;
  from_dt: string;
  to_dt: string;
  total_tickets: number;
  completed_tickets: number;
  canceled_tickets: number;
  no_show_tickets: number;
  avg_wait_seconds: number | null;
  p95_wait_seconds: number | null;
  avg_service_seconds: number | null;
  throughput_per_hour: number;
}

// Auth context
export interface AuthUser {
  sub: string;
  email: string;
  display_name: string;
  tenant_id: string;
  roles: string[];
}
