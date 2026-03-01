"""Auth endpoints – DEV login only (disabled in production)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.security import create_dev_token
from app.schemas.user import DevLoginRequest, TokenResponse

router = APIRouter(tags=["auth"])


@router.post(
    "/dev/login",
    response_model=TokenResponse,
    summary="DEV-only: get a JWT for a pre-seeded user",
)
@limiter.limit("20/minute")
async def dev_login(request: Request, body: DevLoginRequest) -> TokenResponse:
    settings = get_settings()
    if not settings.is_dev:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="/dev/login is only available in development mode",
        )
    token = create_dev_token(str(body.email))
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
    )
