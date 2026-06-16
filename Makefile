# Convenience targets. On Windows, run these via Git Bash, or use the raw
# commands shown in the README if `make` is unavailable.

.PHONY: help install infra-up infra-down stack-up stack-down dev test lint fmt migrate seed train demo-detection

help:
	@echo "install     - create venv and install deps (uv)"
	@echo "infra-up    - start Postgres + Redis only (hybrid dev)"
	@echo "infra-down  - stop infra"
	@echo "stack-up    - start full stack incl. app container (DoD)"
	@echo "stack-down  - stop full stack"
	@echo "dev         - run the API locally with reload"
	@echo "test        - run pytest"
	@echo "lint        - ruff check"
	@echo "fmt         - ruff format"
	@echo "migrate     - apply Alembic migrations"
	@echo "seed        - load synthetic data (M1)"
	@echo "train       - train + export the area-risk model (M3)"
	@echo "demo-detection - run detectors over seeded data (M2)"

install:
	uv venv
	uv pip install -e ".[dev]"

infra-up:
	docker compose up -d postgres redis

infra-down:
	docker compose down

stack-up:
	docker compose --profile app up -d --build

stack-down:
	docker compose --profile app down

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	uv run pytest -q

lint:
	uv run ruff check .

fmt:
	uv run ruff format .

migrate:
	uv run alembic upgrade head

seed:
	uv run python -m scripts.seed

train:
	uv run python -m scripts.train_risk_model

demo-detection:
	uv run python -m scripts.demo_detection
