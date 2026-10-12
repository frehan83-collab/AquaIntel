#!/usr/bin/env bash
set -e

# Run database migrations before starting multi-worker processes
# Prevents Alembic DDL race conditions across gunicorn workers
if [ -f "alembic.ini" ]; then
    echo "[entrypoint] Running database migrations..."
    python -m alembic upgrade head || echo "[entrypoint] WARNING: Alembic migration failed or skipped."
fi

exec "$@"
