"""FastAPI dependency providers."""
from __future__ import annotations

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import TokenPayload, decode_token
from app.db.session import get_db  # re-exported for convenience

security = HTTPBearer(auto_error=False)


def get_redis(request: Request) -> aioredis.Redis:
    """Return the shared Redis client stored on app.state by the lifespan handler."""
    return request.app.state.redis


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> TokenPayload:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await decode_token(credentials.credentials)


async def require_admin(actor: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if not actor.has_role("admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires admin role")
    return actor


async def require_manager(actor: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if not actor.has_role("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires admin or manager role"
        )
    return actor


async def require_staff(actor: TokenPayload = Depends(get_current_user)) -> TokenPayload:
    if not actor.has_role("admin", "manager", "staff"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires staff role or above"
        )
    return actor
