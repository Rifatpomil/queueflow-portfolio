# ADR 0003 – Server-Sent Events vs WebSocket for Signage

**Status:** Accepted
**Date:** 2024-01-01

## Context

Signage boards need to receive live queue updates — "now serving G-0042" — without polling. The update direction is strictly **server → client** (the board never sends data back to the server). The technology choice affects implementation complexity, infrastructure requirements, and long-term maintainability.

## Decision

Use **Server-Sent Events (SSE)** over WebSocket.

## Analysis

| Criterion | SSE | WebSocket |
|-----------|-----|-----------|
| Protocol | HTTP/1.1 (`text/event-stream`) | ws:// (separate handshake) |
| Direction | Server → client only | Bi-directional |
| Browser support | All modern browsers, native `EventSource` API | All modern browsers |
| Nginx/proxy support | Works out of the box (needs `proxy_buffering off`) | Needs `proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade` |
| Auto-reconnect | Built into `EventSource` spec | Must implement manually |
| Load balancer sticky sessions | Not needed (stateless HTTP) | Needed for most LBs |
| TLS termination | Same as any HTTPS request | Same as wss:// |
| FastAPI/Starlette support | `StreamingResponse` built-in | Requires `websockets` library |
| Message format | Text (JSON lines) | Binary or text |
| Multiplexing | One stream per connection | Full duplex |

## Rationale for SSE

1. **The use case is unidirectional.** Signage boards only receive; they never send. WebSocket's bi-directional capability is wasted complexity.

2. **Auto-reconnect is free.** The browser's `EventSource` spec mandates automatic reconnection with exponential backoff. With WebSocket, this must be implemented in client code.

3. **Simpler infrastructure.** SSE flows through standard HTTP proxies without special configuration (only `proxy_buffering off` in nginx). WebSocket requires connection upgrade handling at every proxy hop.

4. **FastAPI makes SSE trivial.** A `StreamingResponse` with an async generator is all that's needed. The full implementation is ~30 lines in `app/services/signage_service.py`.

5. **Redis pub/sub integration is straightforward.** The SSE handler subscribes to `signage:{location_id}`, receives a message, fetches a fresh snapshot, and yields it as a JSON event line. Clean and testable.

## Consequences

- SSE has a browser limit of 6 concurrent connections per origin (HTTP/1.1). This is a non-issue for signage boards (one connection per board, different origins). For HTTP/2, the limit does not apply.
- SSE carries slightly more overhead than WebSocket for very high-frequency updates, but queue signage updates are infrequent (< 1 msg/s per location in normal operation).
- If future requirements need client-to-server communication (e.g., operator keyboard shortcuts on the signage board), this decision should be revisited and WebSocket adopted.

## Heartbeat

A heartbeat comment (`: heartbeat\n\n`) is sent every 30 seconds to prevent proxy idle-connection timeouts (default 60s in many nginx/HAProxy configs).

## Reconnect behaviour and Last-Event-ID

The SSE spec supports a `Last-Event-ID` header that allows clients to resume a stream after a reconnect without missing events. QueueFlow **intentionally does not implement event replay** for the following reasons:

1. **Each reconnect immediately receives a full snapshot.** The first message from `sse_stream()` is always a complete `SignageSnapshot`. A client that drops and reconnects is fully caught up within one message, regardless of what happened during the gap.

2. **Missed events have no lasting effect.** Signage events are ephemeral state snapshots, not commands. Replaying "G-0041 was called 30 seconds ago" to a board that reconnected now provides no value — the board will display G-0041 in `recently_called` from the fresh snapshot anyway.

3. **Event buffering adds operational complexity** (Redis Streams or an in-memory ring buffer) without meaningfully improving the user experience for this use case.

If requirements change such that individual events carry side-effects (e.g., triggering audio announcements exactly once per call), this decision should be revisited and `id:` fields added to SSE events with a Redis Streams-backed replay buffer.
