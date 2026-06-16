#!/usr/bin/env bash
# Container entrypoint: apply migrations, then start the API.
set -euo pipefail

echo "[entrypoint] applying database migrations..."
alembic upgrade head

echo "[entrypoint] starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
