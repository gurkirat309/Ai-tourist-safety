# Frontend — Tourist Safety Control Center

React + Vite + Tailwind CSS v4 UI for the tourist-safety platform. Clean, modern,
map-centric. Consumes the FastAPI backend (see [`../backend`](../backend)).

## Stack
- **React 18** + **Vite 6**
- **Tailwind CSS v4** (via `@tailwindcss/vite`) — slate/blue theme, no purple
- **react-leaflet / Leaflet** — zone polygons + incident/location markers (OSM tiles)
- **react-router-dom** — Dashboard + Tourist Portal
- **lucide-react** — icons

## Views
- **Police Dashboard** (`/`) — stat cards, live Leaflet map (zone polygons coloured
  by risk, incident markers), area-risk lookup, zones list, recent incidents &
  advisory alerts. Auto-refreshes every 15s.
- **Tourist Portal** (`/portal`) — register with DPDP consent, share location
  (or "use my location"), **panic** button; shows the orchestrator's assessment
  (zone, area-risk meter, escalation, detection signals) on a mini map.

## Run (dev)

The backend must be running first (see [`../backend`](../backend)):

```bash
cd backend && docker compose up -d postgres redis && uv run uvicorn app.main:app   # :8000
```

Then the frontend:

```bash
cd frontend
npm install
npm run dev        # http://127.0.0.1:8080
```

The dev server proxies `/api/*` → `http://localhost:8000` (see
[vite.config.js](vite.config.js)), so there's no CORS setup and no hardcoded
backend URL.

> **Windows note:** the dev server uses port **8080** on `127.0.0.1` because the
> default `5173` falls in a WinNAT-reserved port range on some machines (EACCES).

## Build

```bash
npm run build      # -> dist/
npm run preview
```
