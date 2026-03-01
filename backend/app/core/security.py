"""JWT authentication – supports both DEV (local HS256) and Keycloak (RS256)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Token payload schema ──────────────────────────────────────────────────────
DEV_USERS: dict[str, dict[str, Any]] = {
    "admin@queueflow.dev": {
        "sub": "00000000-0000-0000-0000-000000000001",
        "email": "admin@queueflow.dev",
        "display_name": "System Admin",
        "tenant_id": "00000000-0000-0000-0000-000000000010",
        "roles": ["admin"],
    },
    "manager@queueflow.dev": {
        "sub": "00000000-0000-0000-0000-000000000002",
        "email": "manager@queueflow.dev",
        "display_name": "Location Manager",
        "tenant_id": "00000000-0000-0000-0000-000000000010",
        "roles": ["manager"],
    },
    "staff@queueflow.dev": {
        "sub": "00000000-0000-0000-0000-000000000003",
        "email": "staff@queueflow.dev",
        "display_name": "Staff Member",
        "tenant_id": "00000000-0000-0000-0000-000000000010",
        "roles": ["staff"],
    },
    "viewer@queueflow.dev": {
        "sub": "00000000-0000-0000-0000-000000000004",
        "email": "viewer@queueflow.dev",
        "display_name": "Signage Viewer",
        "tenant_id": "00000000-0000-0000-0000-000000000010",
        "roles": ["viewer"],
    },
}


class TokenPayload:
    """Normalised token payload regardless of auth mode."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.sub: str = str(raw.get("sub", ""))
        self.email: str = raw.get("email", raw.get("preferred_username", ""))
        self.display_name: str = raw.get(
            "display_name", raw.get("name", self.email)
        )
        self.tenant_id: str = raw.get("tenant_id", "")
        self.roles: list[str] = self._extract_roles(raw)

    @staticmethod
    def _extract_roles(raw: dict[str, Any]) -> list[str]:
        # Keycloak puts roles in realm_access.roles
        if "realm_access" in raw:
            return raw["realm_access"].get("roles", [])
        # Our DEV tokens store them directly
        return raw.get("roles", [])

    def has_role(self, *roles: str) -> bool:
        return bool(set(self.roles) & set(roles))

    @property
    def user_id(self) -> UUID:
        return UUID(self.sub)


def create_dev_token(email: str) -> str:
    """Issue a short-lived DEV JWT for a pre-seeded user."""
    settings = get_settings()
    user = DEV_USERS.get(email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown DEV user: {email}. "
            f"Valid emails: {list(DEV_USERS.keys())}",
        )
    payload = {
        **user,
        "iat": datetime.now(tz=timezone.utc),
        "exp": datetime.now(tz=timezone.utc)
        + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def decode_token(token: str) -> TokenPayload:
    """Validate a JWT and return the normalised payload."""
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if settings.auth_mode == "dev":
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )
        else:
            # Keycloak RS256 – fetch JWKS on the fly (cached by httpx)
            payload = await _decode_keycloak_token(token)
        return TokenPayload(payload)
    except JWTError as exc:
        logger.warning("jwt_decode_error", error=str(exc))
        raise credentials_exception from exc


async def _decode_keycloak_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.get(settings.keycloak_jwks_url)
        resp.raise_for_status()
        jwks = resp.json()
    # jose handles JWKS verification
    return jwt.decode(token, jwks, algorithms=["RS256"], options={"verify_aud": False})


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
