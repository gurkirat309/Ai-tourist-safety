# AI-Orchestrated Multi-Agent System for Tourist Safety & Incident Intelligence

Monorepo for a platform that monitors tourists in real time, predicts area risk,
detects distress (route deviation, inactivity, signal drop-off, crowding),
watches for risk events, and prepares decision-ready alerts for authorities.

## Layout

```
.
├── backend/         # Python: FastAPI APIs, AI agents, ML pipeline
├── frontend/        # React + Tailwind UI (Police Dashboard + Tourist Portal)
└── DOCUMENTATION.md # full project documentation (architecture, diagrams, data)
```

- **[backend/](backend/)** — FastAPI + agents + ML. See
  [backend/README.md](backend/README.md) for per-milestone docs.
- **[frontend/](frontend/)** — React + Tailwind app (Leaflet map). See
  [frontend/README.md](frontend/README.md).
- **[DOCUMENTATION.md](DOCUMENTATION.md)** — the complete, detailed write-up:
  architecture diagrams, tech-stack rationale, data, and how it was built.

## Architecture (two layers)

- **Fast deterministic detection layer** — geofencing, route deviation,
  inactivity, crowd density. **No LLM in the real-time path.**
- **Agentic LLM intelligence layer** — risk-intelligence + incident-triage
  agents, grounded with `source` / `timestamp` / `confidence`. Advisory only.

## Run locally

### Prerequisites
- **Docker** + **Docker Compose** (for PostgreSQL+PostGIS+pgvector and Redis)
- **[uv](https://docs.astral.sh/uv/)** (Python package manager) — Python 3.11+
- **Node.js 18+** and **npm** (for the frontend)

### 1) Backend (API + agents + ML)

```bash
cd backend

# Configure environment (optional: add a Groq key for the live LLM agent)
cp .env.example .env

# Install Python deps into a virtualenv
uv venv && uv pip install -e ".[dev]"

# Start infrastructure (Postgres+PostGIS+pgvector, Redis)
docker compose up -d postgres redis

# Apply DB migrations, then load synthetic Bengaluru data
uv run alembic upgrade head
uv run python -m scripts.seed

# Train the area-risk model (writes models/area_risk_model.joblib)
uv run python -m scripts.train_risk_model

# Run the API  ->  http://localhost:8000/docs  (interactive OpenAPI)
uv run uvicorn app.main:app --reload
```

Leave that running, then in a **second terminal**:

### 2) Frontend (Dashboard + Tourist Portal)

```bash
cd frontend
npm install
npm run dev        # opens at http://127.0.0.1:8080
```

The dev server proxies `/api/*` → the backend on `:8000`, so no CORS setup is
needed. Open **http://127.0.0.1:8080** — the **Police Dashboard** shows the live
map, zones, incidents, and alerts; the **Tourist Portal** lets you register,
share location, and trigger panic.

### Try it
- In the Tourist Portal: register (keep consent checked), then **Share location**
  near `12.80, 77.577` (the restricted Bannerghatta zone) or hit **Panic** — the
  assessment (zone, risk score, escalation, signals) appears instantly.
- In the Dashboard: click an incident row, an alert, or a map marker to open the
  **incident detail** with recommended actions.

### Optional: explore the milestones via demo scripts
```bash
cd backend
make demo-detection     # the 4 deterministic detectors over seeded trajectories
make demo-triage        # triage a seeded restricted-zone incident
make demo-orchestrator  # stream a trajectory + panic through the orchestrator
make risk-agent         # Risk Intelligence agent (dry-run; --live uses Groq)
make test               # run the test suite

# Optional: the LSTM trajectory-anomaly advisory model (PyTorch)
uv pip install -e ".[lstm]" --torch-backend=cpu
make train-lstm
```

### Notes
- **Groq / LLM:** the agents work in **dry-run mode with no key** (heuristic,
  offline). To use the live LLM, set `LLM_API_KEY` and `LLM_DRY_RUN=false` in
  `backend/.env`. The real-time ingest/panic path stays LLM-free regardless.
- **Windows / corporate networks:** if `uv` installs fail with a TLS cert error,
  prefix commands with `UV_NATIVE_TLS=true` (or set it in `.env`). Postgres is
  mapped to host port **55432** and the frontend runs on **127.0.0.1:8080** to
  avoid Windows reserved-port conflicts — see [DOCUMENTATION.md](DOCUMENTATION.md).
- **Full stack in Docker** (alternative to running the API locally):
  `cd backend && docker compose --profile app up -d --build` (auto-migrates).

Full details, milestones (M0–M7), and architecture: **[backend/README.md](backend/README.md)**
and **[DOCUMENTATION.md](DOCUMENTATION.md)**.
