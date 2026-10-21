# Tourist Safety Companion — mobile app (PWA)

The tourist-facing app: an installable Progressive Web App built with Vite +
React. It is a **separate project** from `frontend/` (the police dashboard), so
the two can evolve and deploy independently.

It is deliberately structured to become a **Capacitor** native app later
without a rewrite — see [Going native](#going-native).

---

## What it does

| Screen | Purpose |
| --- | --- |
| **Signup / Login** | Tourist account, with explicit DPDP consent capture |
| **Safety** (home) | Live status, area-risk meter, zone, route deviation, hold-to-fire SOS, AI voice call |
| **Trip** | Pick start + destination, get a safety-scored route, optional Demo walk |
| **Map** | Risk zones, planned route, live position |
| **Settings** | Emergency number, ping interval, GPS accuracy, privacy, sign out |

Beyond the screens:

- **Safer-route alternatives** — several candidate routes are scored against
  the risk model and the *safest* is recommended, not the fastest, with the
  cost stated plainly ("2 min slower, 49% lower peak risk"). The tourist can
  still choose speed.
- **Risk through the day** — a 24-hour forecast for a place, so "it's fine
  now" and "it's fine at 11pm" are different questions.
- **Nearby advisories** — sanitized risk events from the intelligence agent:
  the kind of thing reported nearby and what to do, never the incident
  details.
- **Crowd + movement-anomaly warnings** — congestion and the LSTM
  trajectory signal now reach the tourist, not just the control room.
- **Real GPS tracking** — `navigator.geolocation.watchPosition`, with fixes
  sent on a time *or* distance trigger so fast movement is not under-sampled.
- **Accuracy filtering** — fixes worse than 200 m are dropped, so a
  cell-tower fix cannot masquerade as a route deviation.
- **Offline queue** — pings that cannot be sent are stored and replayed
  oldest-first on reconnect, each keeping its original timestamp.
- **SOS fallback** — if GPS is unavailable the SOS still sends, using the last
  known position, and says so. It never silently fails.
- **Demo mode** — replays a planned route as simulated movement. Pings are
  tagged `demo` server-side so simulated data is never mistaken for real.

---

## Run it

Prerequisites: the backend running (see `backend/README.md`) with Postgres and
Redis up.

```bash
cd mobile
npm install
cp .env.example .env     # point VITE_API_BASE at your backend
npm run dev              # http://localhost:8081
```

The backend must allow this origin. `CORS_ORIGINS` in `backend/.env` already
includes `http://localhost:8081` and `http://127.0.0.1:8081`.

### Production build

```bash
npm run build            # -> dist/  (includes manifest + service worker)
npm run preview
```

---

## Testing on a real phone (iPhone / Android)

Phones expose geolocation **only on secure (https) origins**, so a plain
`http://192.168.x.x:8081` will silently fail. The simplest working setup is a
single https tunnel in front of the backend, which serves the built app on its
own origin — one tunnel, no CORS, same-origin API calls.

One command does all of it:

```powershell
powershell -ExecutionPolicy Bypass -File backend/start-phone.ps1
```

That starts Postgres + Redis, builds the app, launches ngrok on the fixed
domain, and runs the backend. Then open the printed https URL on the phone.

<details>
<summary>Doing it manually</summary>

```bash
cd mobile && npm run build        # uses .env.production -> same-origin API
cd ../backend && .venv/Scripts/uvicorn app.main:app --host 0.0.0.0 --port 8000
ngrok http 8000 --url=<your-domain>.ngrok-free.dev
```

</details>

### Install it on an iPhone

1. Open the https URL **in Safari** (iOS only allows Add to Home Screen there).
2. ngrok's free tier shows a warning page once — tap **Visit Site**.
3. Tap the **Share** button, then **Add to Home Screen**.
4. Launch it from the home screen. It runs full-screen with no browser chrome.
5. On the first SOS or **Start sharing location**, iOS asks for location —
   choose **Allow While Using App**.

### Notes

- The phone does **not** need to be on the same Wi-Fi — traffic goes through
  the tunnel. Both devices just need internet.
- The laptop must stay running; it is the server.
- `TWILIO_WEBHOOK_BASE_URL` already points at this same domain, so the AI
  voice call keeps working.
- Tunnel URL changed? Rebuild is **not** needed — the app calls its own
  origin, whatever that is.
- ngrok free shows the interstitial once per browser. If it becomes annoying,
  [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
  (`cloudflared tunnel --url http://localhost:8000`) is free and shows no
  warning page.

### iOS limitations to expect

- **Tracking pauses when the app is backgrounded or the screen locks.** This is
  a browser limit, not a bug. Keep the app open and the screen on while
  testing a walk. The fix is the native build.
- No push notifications from an iOS PWA unless installed to the home screen
  (iOS 16.4+), and this app does not implement push yet.

## Going native

The app is written so Capacitor is an incremental step, not a rewrite. All
device access is isolated in two files:

| File | Swap to |
| --- | --- |
| `src/lib/geo.js` | `@capacitor/geolocation` + a background-location plugin |
| `src/lib/storage.js` | `@capacitor/preferences` (and secure storage for the token) |

Nothing else in the app touches `navigator.geolocation` or `localStorage`.

```bash
npm i @capacitor/core @capacitor/cli
npx cap init
npm run build && npx cap add android && npx cap open android
```

**Prerequisites not currently on this machine:** JDK 17+ (Java 8 is installed)
and the Android SDK / Android Studio.

### Why native is worth it

The one thing a PWA genuinely cannot do is **track in the background**. When
the screen locks or the browser is backgrounded, `watchPosition` stops. The app
mitigates this with a screen wake lock while sharing, but for a safety product
that runs in a pocket all day, background location and push notifications are
the reason to go native.

---

## Structure

```
mobile/
  public/icons/        launcher icons (generated)
  src/
    lib/
      api.js           fetch wrapper, typed errors, timeouts
      auth.jsx         auth context; survives being offline
      geo.js           geolocation  <- Capacitor swap point
      storage.js       key/value     <- Capacitor swap point
      queue.js         offline ping queue
      tracking.jsx     the tracking engine (GPS -> backend -> status)
      format.js        shared presentation helpers
    components/        Shell, StatusCard, SosButton, MiniMap, PlacePicker, ui
    pages/             Home, Trip, MapPage, Settings, Login, Signup
```

`src/lib/tracking.jsx` is the heart of the app and the best place to start
reading.

---

## Design notes

- **The app never decides whether you are safe.** It reports position and
  renders the backend's verdict. All detection stays in the deterministic
  server-side layer.
- **SOS is hold-to-fire (~1.6s)**, not tap (too easy in a pocket) and not a
  confirm dialog (too slow in an emergency). Releasing early cancels.
- **Consent is an unticked checkbox** at signup, as DPDP Act 2023 requires
  free, specific and informed consent.
- Tap targets are ≥44px and inputs use 16px text so iOS Safari does not zoom.
