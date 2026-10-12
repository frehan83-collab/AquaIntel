FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# uv — deterministic, locked dependency installs (P0-4)
COPY --from=ghcr.io/astral-sh/uv:0.10 /uv /uvx /bin/

# Python deps (cached layer) — locked by requirements.lock (regenerate from
# pyproject.toml with: uv pip compile pyproject.toml --python-version 3.12
# --python-platform linux -o requirements.lock)
COPY pyproject.toml requirements.lock ./
RUN uv pip install --system --no-cache -r requirements.lock

# App code
COPY . .

# Create dirs, make entrypoint executable + non-root user for security
RUN mkdir -p data/models logs && \
    chmod +x scripts/docker-entrypoint.sh && \
    useradd -m -u 1000 -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

ENTRYPOINT ["/app/scripts/docker-entrypoint.sh"]

# Migrations run once in the entrypoint before workers spawn -> workers skip them
ENV FISHINTEL_RUN_MIGRATIONS=0

# Production: Gunicorn with Uvicorn workers (multi-process, crash recovery)
# Workers = 2 * CPU cores + 1. Override with GUNICORN_WORKERS env var.
# max-requests prevents memory leaks; independent worker event loops (no preload)
CMD ["gunicorn", "core.api:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", \
     "-b", "0.0.0.0:8000", \
     "--max-requests", "10000", \
     "--max-requests-jitter", "1000", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--access-logfile", "-"]
