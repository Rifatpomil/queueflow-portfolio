"""OpenTelemetry tracing and metrics setup.

When OTEL_ENABLED=true, instruments FastAPI and SQLAlchemy.
Exports spans to OTLP collector (e.g. Jaeger, Grafana Tempo).
"""
from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import get_settings


def setup_otel(app: object, engine: object | None = None) -> None:
    """Configure OpenTelemetry tracing. Call after app and engine are created."""
    settings = get_settings()
    if not settings.otel_enabled:
        return

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint,
        insecure=True,
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))

    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="healthz,readyz,metrics,docs,redoc,openapi.json",
    )

    if engine is not None and hasattr(engine, "sync_engine"):
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
