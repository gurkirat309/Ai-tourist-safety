# syntax=docker/dockerfile:1
FROM python:3.11-slim

# uv for fast, reproducible installs
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /code

# System deps for geo/psycopg builds (kept minimal; psycopg uses binary wheels)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# UV_INSECURE=1 is an escape hatch for networks doing TLS interception with a
# custom root CA that isn't in the container trust store (e.g. corporate proxy /
# antivirus). On a normal network leave it unset for full certificate checking.
ARG UV_INSECURE=0
ENV UV_NATIVE_TLS=true

# Copy the full source first: hatchling needs app/ and README.md to build the
# project. (We trade a little layer caching for a correct build.)
COPY . .
RUN if [ "$UV_INSECURE" = "1" ]; then \
        uv pip install --system \
            --allow-insecure-host pypi.org \
            --allow-insecure-host files.pythonhosted.org \
            . ; \
    else \
        uv pip install --system . ; \
    fi

RUN chmod +x docker/entrypoint.sh

EXPOSE 8000

# Applies migrations, then starts the API.
CMD ["docker/entrypoint.sh"]
