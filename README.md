# Tourist Safety — Backend & AI Agents

Backend services, AI agents, and the ML training pipeline for an
**AI-Orchestrated Multi-Agent System for Tourist Safety and Incident
Intelligence**. No frontend in this phase — everything is exposed as APIs or
runnable scripts.

## Architecture (two layers)

- **Fast deterministic detection layer** — geofencing, route deviation,
  inactivity, crowd density. No LLM in this path. (M2)
- **Agentic LLM intelligence layer** — risk-intelligence and incident-triage
  agents, grounded with `source` / `timestamp` / `confidence`. Advisory only;
  agents never dispatch police. (M4–M6)

## Tech stack

Python 3.11+ · FastAPI · Pydantic v2 · PostgreSQL + PostGIS + pgvector ·
SQLAlchemy + GeoAlchemy2 · Alembic · Redis · Shapely/geopy · scikit-learn ·
Groq (OpenAI-compatible, behind a provider-agnostic wrapper).

Dependency management: **uv**. Dev runtime: **hybrid** (Postgres + Redis in
Docker, app run locally).

## Prerequisites

- Docker + Docker Compose v2
- [uv](https://docs.astral.sh/uv/) (`pipx install uv` or see the docs)

## Quick start (hybrid dev)

> **Custom root CA networks** (corporate proxy / antivirus TLS inspection):
> export `UV_NATIVE_TLS=true` (PowerShell: `$env:UV_NATIVE_TLS="true"`) so uv
> trusts your OS certificate store, otherwise installs fail with
> `invalid peer certificate: UnknownIssuer`.

```bash
cp .env.example .env          # adjust if needed
uv venv && uv pip install -e ".[dev]"   # or: make install

docker compose up -d postgres redis     # or: make infra-up

uv run uvicorn app.main:app --reload    # or: make dev
```

Then:

- Liveness:  http://localhost:8000/health
- Readiness: http://localhost:8000/health/ready  (checks Postgres + Redis)
- API docs:  http://localhost:8000/docs

## Database migrations & seed (M1)

```bash
# Apply migrations to the running Postgres
uv run alembic upgrade head            # or: make migrate

# Load synthetic Bengaluru data (zones, tourists, trajectories, risk events)
uv run python -m scripts.seed          # or: make seed
```

The seed creates 6 Bengaluru zones (MG Road, Koramangala, Majestic transit hub,
Cubbon Park, Electronic City, Bannerghatta forest fringe), 4 tourists with
consent + planned routes, and trajectories covering **normal / deviating /
going-silent** scenarios (these double as fixtures for the M2 detection layer).

## Detection layer (M2)

Fast, **deterministic** detectors — no LLM in this path (an LLM hallucinating
"all clear" is the worst-case failure). Each is a pure, unit-tested function in
[app/detection/](app/detection/), with thresholds centralized in
[app/detection/thresholds.py](app/detection/thresholds.py):

- **Geofencing** — point-in-polygon vs zones → restricted (critical) / high-risk (warning) entry.
- **Route deviation** — geodesic distance from the planned route + a speed sanity check.
- **Inactivity / drop-off** — time since last ping, **tightened in higher-risk zones**.
- **Crowd density** — recent pings vs a zone's capacity, plus a geohash hotspot helper.

See them run over the seeded Bengaluru trajectories (also shows the M3 risk score
per tourist, previewing how M6 will combine them):

```bash
uv run python -m scripts.demo_detection     # or: make demo-detection
```

## Area-risk model (M3)

The only trained model in the system: a spatiotemporal risk-probability model for
Bengaluru. India has no public point-level crime data, so we use **real
NCRB / data.gov.in aggregates as zone-level priors** ([app/ml/bengaluru_priors.py](app/ml/bengaluru_priors.py))
and generate **synthetic geocoded + timestamped incidents** conditioned on them
([app/ml/dataset.py](app/ml/dataset.py)), then train a classical
`HistGradientBoostingClassifier`.

```bash
uv run python -m scripts.train_risk_model     # or: make train
```

This builds the dataset, trains, prints metrics (ROC-AUC / average precision),
saves `models/area_risk_model.joblib`, and runs a sanity check. Inference:

```python
from datetime import datetime, UTC
from app.ml.risk_model import predict_risk
predict_risk(12.9770, 77.5720, datetime(2026, 6, 20, 22, tzinfo=UTC))  # -> 0..1
```

The score is the probability of an incident in that grid cell within the next
few hours, given location, time-of-day/day-of-week, the zone prior, and recent
incident counts. A Colab-friendly notebook is in
[notebooks/risk_model_training.ipynb](notebooks/risk_model_training.ipynb).

The numeric priors are **approximate, NCRB-informed, and easy to tune** — edit
`ZONE_PRIORS` / the temporal multipliers as better figures become available.

## Full stack in Docker (Definition of Done)

The app container applies migrations on startup, then serves the API.

```bash
docker compose --profile app up -d --build   # or: make stack-up
curl http://localhost:8000/health
docker compose run --rm app python -m scripts.seed   # populate synthetic data
```

> On a TLS-intercepting network, build with `UV_INSECURE=1 docker compose
> --profile app up -d --build` (see `.env` / `.env.example`).

## Tests

```bash
uv run pytest -q   # or: make test
```

M0 tests run with **no infra** required (Postgres/Redis are mocked).

## Configuration

All settings come from environment variables — see [.env.example](.env.example).
Secrets are never hardcoded. The LLM provider is swappable via `LLM_PROVIDER`,
`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`; leave the key blank / `LLM_DRY_RUN=true`
to run agents in mock mode without network access.

## Privacy (DPDP Act 2023)

Location data is sensitive personal data. The schema models consent, purpose,
and retention from the start, with a retention/expiry path. Raw coordinates are
not logged at INFO or above.

## Milestones

- [x] **M0 — Scaffold:** repo, config, logging, Docker infra, `/health`, tests.
- [x] **M1 — Data layer:** models, schemas, migrations, retention helper, synthetic seed.
- [x] **M2 — Fast detection layer:** geofencing, route deviation, inactivity, crowd density (deterministic, no LLM).
- [x] **M3 — Area risk model:** Bengaluru priors + synthetic incidents, trained GBM, `predict_risk` inference.
- [ ] M4 — Risk Intelligence agent.
- [ ] M5 — Incident Triage agent.
- [ ] M6 — Orchestrator + escalation.
- [ ] M7 — Backend APIs.
