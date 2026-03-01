"""Redis-backed rate limiting via SlowAPI."""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings


def _get_key_func(request):  # type: ignore[no-untyped-def]
    """Rate-limit key: IP address (or X-Forwarded-For in prod)."""
    return get_remote_address(request)


settings = get_settings()

limiter = Limiter(
    key_func=_get_key_func,
    storage_uri=settings.redis_url,
    enabled=settings.rate_limit_enabled,
)
