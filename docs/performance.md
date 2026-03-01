# Performance Notes

## Target SLOs

| Metric | Target |
|--------|--------|
| `POST /v1/tickets` p99 latency | < 50ms |
| `POST /counters/{id}/call-next` p99 | < 30ms |
| `GET /v1/signage/{id}` p99 | < 20ms |
| SSE first-event delivery | < 500ms |
| Throughput (single API pod) | > 500 RPS |

## Critical Paths and Optimisations

### call-next (hot path)
- Uses `SELECT … FOR UPDATE SKIP LOCKED` — O(log n) with composite index
- Runs in a single transaction; no N+1 queries
- Expected latency: 5–15ms for a queue of 10,000 tickets

### Ticket creation
- Number allocation is atomic within the INSERT transaction
- Idempotency check is a single indexed read
- Redis PUBLISH is fire-and-forget (best-effort, non-blocking)

### Signage snapshot
- Four queries, all using indexed columns
- Result is pushed through SSE without DB polling on the client side
- In high-throughput environments, the snapshot could be cached in Redis (TTL 1s)

## Load Test Reference (k6 script)

```javascript
// scripts/load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '30s', target: 50 },
    { duration: '60s', target: 200 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(99)<100'],
    http_req_failed: ['rate<0.01'],
  },
};

const BASE = 'http://localhost:8000';

export function setup() {
  const login = http.post(`${BASE}/dev/login`, JSON.stringify({
    email: 'staff@queueflow.dev'
  }), { headers: { 'Content-Type': 'application/json' } });
  return { token: login.json('access_token') };
}

export default function (data) {
  const headers = {
    'Authorization': `Bearer ${data.token}`,
    'Content-Type': 'application/json',
  };
  const r = http.post(`${BASE}/v1/tickets`, JSON.stringify({
    location_id: '00000000-0000-0000-0000-000000000020',
  }), { headers });
  check(r, { 'ticket created': (r) => r.status === 201 });
  sleep(0.1);
}
```

Run with: `k6 run scripts/load-test.js`

## Connection Pool Tuning

```env
# backend/.env
DB_POOL_SIZE=10        # baseline connections per pod
DB_MAX_OVERFLOW=20     # burst headroom
```

For 4 API workers × (10+20) = 120 max Postgres connections.
PostgreSQL default `max_connections=100` should be raised to 200+ in production.

## Async I/O

The API uses `asyncpg` (async Postgres driver) throughout. Under a 200-RPS load,
a single Uvicorn worker can handle hundreds of concurrent in-flight requests
while waiting on DB I/O, because the event loop is never blocked.

Celery workers use synchronous `psycopg2` (blocking I/O acceptable for background tasks).
