# ──────────────────────────────────────────────────────────────────────────────
# QueueFlow Backend – multi-stage Dockerfile
# ──────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc curl && \
    rm -rf /var/lib/apt/lists/*

# ── Development stage ─────────────────────────────────────────────────────────
FROM base AS development

COPY pyproject.toml .
RUN pip install -e ".[dev]"

# Copy source after deps for better cache reuse
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production stage ──────────────────────────────────────────────────────────
FROM base AS production

COPY pyproject.toml .
RUN pip install .

COPY . .

# Create non-root user
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4", "--proxy-headers", "--forwarded-allow-ips", "*"]
