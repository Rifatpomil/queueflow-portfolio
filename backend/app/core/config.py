"""Application configuration – driven entirely by environment variables."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    app_env: Literal["development", "production", "test"] = "development"
    app_name: str = "QueueFlow"
    app_version: str = "0.1.0"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://queueflow:queueflow_dev_secret@localhost:5432/queueflow"
    database_sync_url: str = "postgresql+psycopg2://queueflow:queueflow_dev_secret@localhost:5432/queueflow"
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Celery ────────────────────────────────────────────────────────────────
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Auth ──────────────────────────────────────────────────────────────────
    auth_mode: Literal["dev", "keycloak"] = "dev"
    jwt_secret_key: str = "dev-super-secret-key-change-in-prod-32chars"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Keycloak (only used when auth_mode == "keycloak")
    keycloak_url: str = "http://localhost:8080"
    keycloak_realm: str = "queueflow"
    keycloak_client_id: str = "queueflow-api"
    keycloak_client_secret: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    # ── Rate limiting ─────────────────────────────────────────────────────────
    rate_limit_enabled: bool = True

    # ── OpenTelemetry ─────────────────────────────────────────────────────────
    otel_enabled: bool = False
    otel_service_name: str = "queueflow-api"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    # ── RLS (Postgres Row-Level Security) ──────────────────────────────────────
    rls_enabled: bool = False

    # ── AI (Groq free tier / OpenAI-compatible) ──────────────────────────────────
    ai_api_key: str = ""
    ai_provider: Literal["groq", "openai", "mock"] = "mock"
    ai_base_url: str = ""  # For OpenAI-compatible custom endpoints

    # ── Derived helpers ───────────────────────────────────────────────────────
    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def keycloak_jwks_url(self) -> str:
        return (
            f"{self.keycloak_url}/realms/{self.keycloak_realm}"
            "/protocol/openid-connect/certs"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
