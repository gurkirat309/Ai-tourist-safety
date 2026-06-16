# Frontend (planned)

The tourist portal and police dashboard UI will live here.

**Not built yet** — this phase is backend + AI agents + ML only. This folder is a
placeholder so the repo is organized for the UI work to come.

## Planned stack
- React + Vite
- Tailwind CSS
- Consumes the backend API (FastAPI, see [`../backend`](../backend)) — OpenAPI
  docs at `http://localhost:8000/docs` when the backend is running.

## Likely views
- **Tourist portal** — registration/consent, live location sharing, panic button.
- **Police dashboard** — map of zones/risk, live incidents & alerts, triage detail.

When we start: `npm create vite@latest . -- --template react` then add Tailwind.
