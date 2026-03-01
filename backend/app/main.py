"""
QueueFlow – FastAPI application entry point.

Lifecycle
---------
startup:  configure logging, verify DB + Redis connections
shutdown: close connections

Middleware
----------
- CORS (configured from settings)
- Request-ID injection (UUID per request, attached to log context)
- Rate limiter (SlowAPI)
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import structlog

from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.auth import router as auth_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.rate_limit import limiter
from app.state_machine.ticket_fsm import InvalidTransitionError

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup → yield → shutdown."""
    logger.info(
        "queueflow_starting",
        version=settings.app_version,
        env=settings.app_env,
        auth_mode=settings.auth_mode,
    )

    # Verify DB connectivity
    try:
        from app.db.session import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("db_connected")
    except Exception as exc:
        logger.warning("db_not_ready", error=str(exc))

    # Create shared Redis client — one connection pool reused by all requests
    import redis.asyncio as aioredis
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        await app.state.redis.ping()
        logger.info("redis_connected")
    except Exception as exc:
        logger.warning("redis_not_ready", error=str(exc))

    yield

    logger.info("queueflow_stopping")
    from app.db.session import engine
    await engine.dispose()
    await app.state.redis.aclose()


app = FastAPI(
    title="QueueFlow API",
    description=(
        "Multi-site Queue Orchestration Platform with Real-Time Signage, RBAC, and Analytics"
    ),
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── OpenTelemetry tracing (when OTEL_ENABLED=true) ────────────────────────────
if settings.otel_enabled:
    from app.db.session import engine
    from app.core.otel import setup_otel
    setup_otel(app, engine)

# ── Rate limiter ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


# ── RLS context middleware (sets tenant_id / signage_location_id for get_db) ───
@app.middleware("http")
async def rls_context_middleware(request: Request, call_next):
    """When RLS_ENABLED, set request.state for Postgres session variables."""
    if settings.rls_enabled:
        # Signage: /v1/signage/{location_id} or /v1/signage/{location_id}/stream
        if request.url.path.startswith("/v1/signage/"):
            parts = request.url.path.rstrip("/").split("/")
            if len(parts) >= 4:  # /v1/signage/{uuid}
                try:
                    request.state.signage_location_id = parts[3]
                except (IndexError, ValueError):
                    pass
        # Auth: decode JWT and set tenant_id for authenticated requests
        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            try:
                from app.core.security import decode_token
                payload = await decode_token(auth[7:])
                request.state.tenant_id = payload.tenant_id
            except Exception:
                pass
    return await call_next(request)


# ── Request-ID middleware ─────────────────────────────────────────────────────
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-API-Version"] = "1"
    return response


# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(InvalidTransitionError)
async def invalid_transition_handler(request: Request, exc: InvalidTransitionError):
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(v1_router)

# ── Prometheus metrics (/metrics) ─────────────────────────────────────────────
# Exposes RED metrics (rate, errors, duration) per endpoint.
# In production, scrape this with Prometheus; exclude from public internet.
Instrumentator(
    should_group_status_codes=False,
    excluded_handlers=["/healthz", "/readyz", "/metrics"],
).instrument(app).expose(app, include_in_schema=False, tags=["observability"])


# ── Health / readiness ────────────────────────────────────────────────────────
@app.get("/healthz", tags=["health"], summary="Liveness probe")
async def healthz() -> dict:
    return {
        "status": "ok",
        "version": settings.app_version,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


@app.get("/readyz", tags=["health"], summary="Readiness probe (DB + Redis)")
async def readyz(request: Request) -> dict:
    """K8s readiness: 200 = ready for traffic, 503 = not ready."""
    import time

    checks: dict[str, dict[str, str | float]] = {}

    # DB
    start = time.perf_counter()
    try:
        from app.db.session import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["db"] = {"status": "ok", "latency_ms": round((time.perf_counter() - start) * 1000, 1)}
    except Exception as exc:
        checks["db"] = {"status": "error", "message": str(exc)}

    # Redis (use shared pool from app.state)
    start = time.perf_counter()
    try:
        r = getattr(request.app.state, "redis", None)
        if r is None:
            checks["redis"] = {"status": "error", "message": "Redis not initialized"}
        else:
            await r.ping()
            checks["redis"] = {"status": "ok", "latency_ms": round((time.perf_counter() - start) * 1000, 1)}
    except Exception as exc:
        checks["redis"] = {"status": "error", "message": str(exc)}

    all_ok = all(c.get("status") == "ok" for c in checks.values())
    return JSONResponse(
        status_code=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ok" if all_ok else "degraded",
            "version": settings.app_version,
            "checks": checks,
        },
    )
