# Security

## Threat Model

### Assets to protect
1. **Customer data** – ticket records, wait times, personal notes
2. **Operational access** – ability to call/complete/cancel tickets
3. **Tenant isolation** – data from one organization must never leak to another
4. **Admin functions** – creating users, locations, changing roles

### Threat actors
| Actor | Description | Risk level |
|-------|-------------|------------|
| Unauthenticated public user | Can access signage endpoints only | Low |
| Authenticated staff | Can manipulate tickets at their location | Medium |
| Malicious insider | Has valid credentials, abuses their role | High |
| External attacker | No credentials, network access only | High |

---

## Authentication

### DEV mode (default)
- Local HS256 JWTs issued by the `/dev/login` endpoint
- Endpoint is disabled (`404`) when `APP_ENV != development`
- Secrets stored in environment variables (never in code)

### Production mode (`AUTH_MODE=keycloak`)
- JWT issued by Keycloak (RS256), validated against JWKS endpoint
- The API only validates tokens — it never stores passwords
- Keycloak realm configuration is imported at startup from `keycloak/realm-export.json`

### Token payload normalisation
Both modes produce a `TokenPayload` object with identical fields (`sub`, `email`, `tenant_id`, `roles`). Service layer code is auth-mode agnostic.

---

## Authorisation (RBAC)

| Role | Permissions |
|------|-------------|
| `admin` | Full access: CRUD tenants, locations, users, roles; all ticket operations |
| `manager` | CRUD locations, services, counters; all ticket operations |
| `staff` | Create/call/serve/complete/cancel tickets |
| `viewer` | Read-only; signage display (no auth required for public signage) |

**Enforcement layers:**
1. **Dependency injection** (`app/api/deps.py`): `require_admin`, `require_manager`, `require_staff` FastAPI dependencies
2. **Service layer** (`app/services/`): all service methods re-check roles before executing
3. **Tenant isolation**: every DB query filters by `tenant_id` from the JWT

Signage endpoints are intentionally **public** (no auth) — they are designed to be displayed on public screens.

---

## API Security Controls

### Rate limiting
- Implemented via `SlowAPI` backed by Redis
- `/dev/login`: 20 requests/minute per IP
- `POST /v1/tickets`: 60 requests/minute per IP
- Configurable via `RATE_LIMIT_ENABLED` env var (disabled in tests)

### CORS
- Configured via `CORS_ORIGINS` environment variable
- Defaults to `localhost` origins only
- Production deployments should set explicit allowed origins

### Idempotency
- `Idempotency-Key` header on `POST /v1/tickets` prevents duplicate ticket creation
- Request body hash stored alongside the key; mismatched body returns `422`
- Keys expire after 24 hours; cleaned up by background job

### Input validation
- All request bodies validated by Pydantic v2 models (strict type checking)
- Enum validation for status fields
- Range validation for `priority` (1–10)
- Email format validation via `pydantic[email]`

### SQL injection
- SQLAlchemy ORM with parameterised queries throughout
- No raw SQL string formatting anywhere
- Only `text()` expressions with named parameters in analytics queries

### XSS / Content Security
- API returns JSON only (no HTML rendering)
- Frontend uses React's built-in JSX escaping

---

## Secrets Management

| Secret | Storage |
|--------|---------|
| `JWT_SECRET_KEY` | Environment variable, never in code |
| `POSTGRES_PASSWORD` | Docker secrets / env var |
| Database credentials | Connection strings via env var only |
| Keycloak client secret | Env var |

`.env.example` contains only placeholder values. `.env` is in `.gitignore`.

---

## Audit Log

All privileged actions are written to the `audit_log` table:
- `Tenant` create/update
- `User` create / role assignment
- `Location` create/update
- Every action includes: `actor_user_id`, `tenant_id`, `action`, `object_type`, `object_id`, `before_json`, `after_json`, `created_at`

The audit log is append-only. No UPDATE or DELETE operations are performed on it.

---

## Mitigations Summary

| Threat | Mitigation |
|--------|-----------|
| Token forgery | RS256 / HS256 signature validation; short expiry (60 min) |
| Cross-tenant data access | `tenant_id` filter on every query; service-layer check |
| Privilege escalation | RBAC checked at both router and service layer |
| Brute-force login | Rate limiting on `/dev/login` |
| Ticket duplication under concurrent load | `SELECT FOR UPDATE SKIP LOCKED` + transactions |
| Double-submission | Idempotency key with SHA-256 body hash |
| DDoS / abuse | Redis-backed rate limiting per IP |
| Secrets in code | Env-var-driven config; `.env` in `.gitignore` |
| SQL injection | SQLAlchemy ORM parameterised queries |
| Signage scraping | Signage is intentionally public; contains no PII |
