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

## Quick start (backend)

```bash
cd backend
cp .env.example .env
uv venv && uv pip install -e ".[dev]"
docker compose up -d postgres redis
uv run alembic upgrade head && uv run python -m scripts.seed
uv run uvicorn app.main:app --reload     # http://localhost:8000/docs
```

Full details, milestones (M0–M7), and demo scripts: **[backend/README.md](backend/README.md)**.
