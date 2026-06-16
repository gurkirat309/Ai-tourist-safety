# Claude Code Brief — Tourist Safety: Backend & AI Agents

You are building the backend and AI/ML core of an **AI-Orchestrated Multi-Agent System for Tourist Safety and Incident Intelligence**. This brief is your starting context. Read it fully, then propose a plan before writing large amounts of code.

---

## 1. What the system is

A platform that monitors tourists in real time, predicts how risky their location is, detects distress (route deviation, inactivity, signal drop-off), watches crowd density, and prepares decision-ready alerts for authorities. There are two future interfaces (a tourist portal and a police dashboard), but **we are not building any UI in this phase.**

## 2. Your mission for this phase

Build the **backend services, the AI agents, and the ML training pipeline** — everything except the frontend. By the end of this phase the system should be able to ingest tourist location data, run real-time risk/anomaly detection, train and serve the area-risk model, run the AI agents, and expose backend APIs that a UI could later consume.

**Explicitly out of scope right now:** React/frontend, maps UI, dashboards, styling. Do not build these. If something needs a frontend to be testable, expose it as an API endpoint and/or a CLI/test script instead.

## 3. Architectural principles (these are hard rules)

- **Hybrid design.** There are two layers: a *fast deterministic detection layer* and an *agentic LLM intelligence layer*. Keep them separate.
- **No LLM in the real-time alert path.** Route deviation, inactivity, crowd density, and geofencing must be fast, deterministic code (rules/geometry/aggregation or classical ML) — never an LLM call. An LLM hallucinating "all clear" is the worst-case failure.
- **Agents must be grounded.** Every risk signal an agent emits carries a `source`, a `timestamp`, and a `confidence` score. No free-form guesses.
- **Orchestration is explicit and debuggable.** Use plain Python control flow / function-calling. Do NOT use heavy agent frameworks (LangChain/LangGraph) for the control flow. Agents never autonomously dispatch police — their output is decision support for humans.
- **Privacy-first (DPDP Act 2023).** Location data is sensitive personal data. Model consent, purpose, and retention from the start; include a data-minimization/expiry path. Don't log raw location more than necessary.
- **Build incrementally with tests.** One module at a time, each with tests and a runnable demo script. Don't scaffold everything at once.
- **Ask before you execute — this is mandatory.** Do not write implementation code or run commands until you have (a) asked me any clarifying questions, (b) presented a short plan for the milestone you're about to start, and (c) received my explicit go-ahead. When anything is ambiguous, ask rather than assume. When there's a meaningful decision (a library choice, a schema shape, a tradeoff), surface 2–3 options with a recommendation and let me pick. Prefer asking a few sharp questions over guessing.
- **Never block on real data.** Where a real dataset isn't available in this environment, generate realistic synthetic data so the pipeline is fully runnable end to end.

## 4. Tech stack (use these)

- **Language/runtime:** Python 3.11+
- **API:** FastAPI + Uvicorn, Pydantic v2
- **DB:** PostgreSQL + PostGIS (geospatial), accessed via SQLAlchemy + GeoAlchemy2; Alembic for migrations
- **Cache / realtime bus:** Redis (live location cache, pub/sub)
- **Vector store:** pgvector (for agent-retrieved risk-event embeddings)
- **Geo math:** Shapely, geopy
- **ML:** scikit-learn, XGBoost or LightGBM, pandas, geopandas, numpy; models exported with joblib. These are classical/tabular models — no GPU, no deep learning unless justified.
- **Agents / LLM:** **Groq (free tier)** is the default provider for now. Groq exposes an **OpenAI-compatible API**, so use the OpenAI Python SDK pointed at Groq's `base_url` (or the `groq` SDK) **behind a thin provider-agnostic wrapper** — provider, `base_url`, model name, and API key all come from env. Switching off Groq later must be an env change, not a code change. Pick the current model from Groq's console (don't hardcode a model that may be deprecated). Mind the free-tier rate limits: batch/throttle agent calls and cache results. Also: `feedparser` for RSS, `httpx` + `beautifulsoup4` for fetching/parsing, optional Playwright only if a source needs JS.
- **Scheduling:** APScheduler (periodic agent runs)
- **Infra:** Docker + docker-compose for Postgres/PostGIS + Redis + app. Provide a `.env.example`.
- **Testing:** pytest.

## 5. Build order (milestones)

Work through these in order. **Before starting each milestone, ask me any open questions and present a brief plan, then wait for my approval before writing code.** After each milestone, stop, summarize what you built, show how to run/test it, and check in before moving on.

**M0 — Scaffold.** Repo structure, `pyproject.toml`/requirements, docker-compose (Postgres+PostGIS, Redis), `.env.example`, settings/config module, logging, a health endpoint, and a `make`/script to bring everything up. Get a trivial FastAPI app running in Docker.

**M1 — Data layer.** Define DB models and Pydantic schemas for: `tourists` (with consent fields), `location_pings` (geometry + timestamp), `zones` (PostGIS polygons, risk category, restricted flag), `risk_events` (geo-tagged, with source/timestamp/confidence + embedding), `incidents`, and `alerts`. Add Alembic migrations and a seed script with synthetic tourists, zones, and trajectories.

**M2 — Fast detection layer (deterministic, no LLM).** Build as independent, unit-tested services:
- *Geofencing:* point-in-polygon checks against zones (restricted/remote entry).
- *Route deviation:* distance of actual position from a planned route + speed checks; flag significant deviation.
- *Inactivity / drop-off:* time-since-last-ping anomaly, with thresholds that tighten in higher-risk zones.
- *Crowd density:* aggregate live pings per geohash/zone vs. a capacity threshold; flag congestion.
Include a synthetic-trajectory generator (normal + deviating + going-silent cases) to test these.

**M3 — Area risk model (the only trained model).** A training pipeline (a script and/or a Colab-friendly notebook) that builds a spatiotemporal risk-probability model. Prototype on geocoded open crime data (e.g., Chicago / UK police.uk street-level) using features like location cell, time-of-day, day/season, and recent incident counts; treat Indian NCRB aggregates as zone-level priors. Export with joblib and expose an inference function/service that returns a risk score for a (location, time). If no dataset is present, generate a synthetic labeled dataset so the pipeline runs end to end.

**M4 — Risk Intelligence agent.** Fetches current risk signals (news/RSS, advisories; pluggable sources), uses the LLM to extract structured, geo-tagged `risk_events` (incident type, location, time), and writes them to the DB + pgvector with `source`, `timestamp`, and `confidence`. Runs on a schedule per zone. Make sources pluggable and mockable for tests. Build the LLM call through the provider-agnostic wrapper (Groq by default) and add a dry-run mode that uses canned input so the agent is fully testable without network or API keys. Respect Groq free-tier rate limits — throttle scheduled runs and avoid re-processing unchanged sources.

**M5 — Incident Triage agent.** Given a flagged incident, gathers context (nearby risk_events, zone info, recent pings), produces a concise human-readable summary, and recommends an escalation level. Output is structured and advisory only.

**M6 — Orchestrator + escalation.** Explicit controller that, on each location update, runs the detection layer, consults current zone risk (M3 + M4 signals), applies escalation thresholds, creates `alerts`/`incidents`, and invokes the triage agent when needed. Handle the panic-button path as an immediate, threshold-bypassing escalation. Keep all decisions logged and traceable.

**M7 — Backend APIs (no UI).** FastAPI endpoints a future frontend would use: ingest location pings, register/consent a tourist, query zone/area risk, trigger panic, and list incidents/alerts for authorities. WebSocket endpoint for live updates is fine, but no frontend. Document with the auto OpenAPI docs.

## 6. Suggested repo structure

```
tourist-safety/
  app/
    api/            # FastAPI routers (no UI)
    core/           # config, logging, security
    db/             # models, session, migrations
    schemas/        # Pydantic
    detection/      # geofence, deviation, inactivity, crowd  (deterministic)
    ml/             # area-risk training + inference
    agents/         # risk_intelligence, incident_triage  (LLM)
    orchestrator/   # explicit control flow + escalation
    services/       # alerts, redis, embeddings
  scripts/          # seed data, synthetic generators, demos
  notebooks/        # Colab-friendly model training
  tests/
  docker-compose.yml
  .env.example
  README.md
```

## 7. Conventions

- Type hints everywhere; Pydantic for all I/O boundaries.
- Each module ships with pytest tests and a short demo script under `scripts/`.
- All secrets via environment variables; never hardcode keys. For the LLM, expose `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in `.env.example` (defaulting to Groq), so the provider is swappable. LLM/agent code must run in a mocked/dry-run mode without real keys for tests.
- Keep functions small and the orchestrator readable — favor clarity over cleverness.
- Update the `README.md` as you go with run instructions per milestone.

## 8. How to start

**Do not write code or run anything yet.** Begin by doing only this:

1. Confirm you've understood the scope (backend + agents + model; **no UI**).
2. Ask me your clarifying questions — anything ambiguous in the brief, and especially anything about M0–M1 (repo tooling, exact data model fields, Docker setup, env). Group them so I can answer in one pass.
3. List any meaningful decisions with 2–3 options and your recommendation, and let me choose.
4. Present a short plan and the proposed file scaffold for **M0 and M1 only**.

Then **wait for my explicit go-ahead.** Only after I approve should you implement M0–M1. From there, proceed milestone by milestone, and at the start of every milestone repeat the same loop: questions → plan → my approval → implement → show what's runnable → check in.

**Definition of done for this first chunk (M0–M1):** `docker-compose up` brings up Postgres+PostGIS, Redis, and the API; migrations apply; the seed script populates synthetic tourists, zones, and trajectories; a health endpoint and the DB models are tested. Then we confirm together before continuing to M2.
