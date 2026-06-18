import { useEffect, useRef, useState } from "react";
import {
  Siren,
  Route as RouteIcon,
  Play,
  Square,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { api } from "../lib/api";
import { SEVERITY_STYLES, riskLevel, titleCase } from "../lib/format";
import { Card, Badge, Button, Spinner, Empty } from "../components/ui";
import ZoneMap from "../components/ZoneMap";
import PlacePicker from "../components/PlacePicker";
import AssistantWidget from "../components/AssistantWidget";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const STATUS_TONE = {
  safe: "bg-emerald-100 text-emerald-700 ring-emerald-200",
  warning: "bg-amber-100 text-amber-800 ring-amber-200",
  critical: "bg-red-100 text-red-700 ring-red-200",
  no_data: "bg-slate-100 text-slate-600 ring-slate-200",
};

export default function TouristPortal() {
  const [geojson, setGeojson] = useState(null);
  const [status, setStatus] = useState(null);
  const [trip, setTrip] = useState(null);
  const [places, setPlaces] = useState([]);
  const [start, setStart] = useState(null); // { name, lat, lon }
  const [dest, setDest] = useState(null); // { name, lat, lon }
  const [pos, setPos] = useState(null); // current marker {lat,lon}
  const [busy, setBusy] = useState(null);
  const [deviate, setDeviate] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [err, setErr] = useState(null);
  const stopRef = useRef(false);

  async function loadStatus() {
    try {
      const s = await api.myStatus();
      setStatus(s);
      if (s.last_position) setPos(s.last_position);
    } catch (e) {
      setErr(e.message);
    }
  }

  useEffect(() => {
    api.zonesGeojson().then(setGeojson).catch(() => {});
    api.places().then((d) => setPlaces(d.places || [])).catch(() => {});
    loadStatus();
  }, []);

  async function planTrip() {
    if (!start || !dest) {
      setErr("Pick a start and a destination first.");
      return;
    }
    setBusy("plan");
    setErr(null);
    try {
      const t = await api.planTrip({
        start: { lat: Number(start.lat), lon: Number(start.lon) },
        destination: { lat: Number(dest.lat), lon: Number(dest.lon) },
      });
      setTrip(t);
      setPos({ lat: Number(start.lat), lon: Number(start.lon) });
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  }

  async function sendPing(lat, lon) {
    await api.myPing({ location: { lat, lon } });
    await loadStatus();
  }

  async function panic() {
    const p = pos || start;
    if (!p) {
      setErr("Share a location (pick a start or send your location) before panic.");
      return;
    }
    setBusy("panic");
    setErr(null);
    try {
      await api.myPanic({ location: { lat: Number(p.lat), lon: Number(p.lon) } });
      await loadStatus();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  }

  async function simulate() {
    if (!trip?.route?.length) return;
    setSimulating(true);
    stopRef.current = false;
    setErr(null);
    // Sample ~10 points along the route for a snappy demo.
    const pts = trip.route;
    const step = Math.max(1, Math.floor(pts.length / 10));
    const sampled = pts.filter((_, i) => i % step === 0);
    try {
      for (let i = 0; i < sampled.length; i++) {
        if (stopRef.current) break;
        let [lat, lon] = sampled[i];
        if (deviate && i > sampled.length / 2) {
          // Drift progressively north to trigger route-deviation.
          lat += 0.0025 * (i - sampled.length / 2);
        }
        setPos({ lat, lon });
        await sendPing(lat, lon);
        await sleep(900);
      }
    } catch (e) {
      setErr(e.message);
    } finally {
      setSimulating(false);
    }
  }

  // A few quick-pick destination chips from the curated list.
  const quickPicks = places
    .filter((p) =>
      ["Cubbon Park", "Lalbagh Botanical Garden", "Bangalore Palace",
       "Bannerghatta National Park", "MG Road"].includes(p.name)
    );

  const routeColor = trip ? riskLevel(trip.safety.max_score).color : "#2563eb";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">My Safety</h1>
        <p className="text-sm text-slate-500">
          Plan a route, see how safe it is, and share your location while you travel.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Left controls */}
        <div className="space-y-6">
          <StatusCard status={status} />

          <Card title="Plan a trip">
            <div className="space-y-3">
              <PlacePicker
                label="Starting point"
                value={start}
                onChange={setStart}
                curated={places}
                allowMyLocation
                placeholder="Where are you now?"
              />
              <PlacePicker
                label="Destination"
                value={dest}
                onChange={setDest}
                curated={places}
                placeholder="Where do you want to go?"
              />

              {quickPicks.length > 0 && (
                <div>
                  <div className="mb-1 text-xs font-medium text-slate-400">Popular destinations</div>
                  <div className="flex flex-wrap gap-2">
                    {quickPicks.map((p) => (
                      <button
                        key={p.name}
                        onClick={() => setDest({ name: p.name, lat: p.lat, lon: p.lon })}
                        className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600 transition hover:bg-brand-50 hover:text-brand-700"
                      >
                        {p.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <Button onClick={planTrip} disabled={busy === "plan"} className="w-full">
                {busy === "plan" ? <Spinner /> : <RouteIcon size={16} />} Plan route
              </Button>

              {trip && (
                <div className="rounded-lg bg-slate-50 p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Route safety</span>
                    <span className="font-semibold" style={{ color: routeColor }}>
                      {trip.safety.label}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-slate-400">
                    {(trip.distance_m / 1000).toFixed(1)} km · ~{Math.round(trip.duration_s / 60)} min · {trip.source}
                  </div>
                </div>
              )}
            </div>
          </Card>

          <Card title="Travel">
            <label className="mb-3 flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" checked={deviate} onChange={(e) => setDeviate(e.target.checked)}
                     className="h-4 w-4 accent-brand-600" />
              Simulate going off-route
            </label>
            <div className="grid grid-cols-2 gap-2">
              {!simulating ? (
                <Button onClick={simulate} disabled={!trip} className="w-full">
                  <Play size={16} /> Start trip
                </Button>
              ) : (
                <Button variant="ghost" onClick={() => (stopRef.current = true)} className="w-full">
                  <Square size={16} /> Stop
                </Button>
              )}
              <Button variant="danger" onClick={panic} disabled={busy === "panic"} className="w-full">
                {busy === "panic" ? <Spinner /> : <Siren size={16} />} Panic
              </Button>
            </div>
            {err && <p className="mt-2 text-sm text-red-600">{err}</p>}
            <p className="mt-2 text-xs text-slate-400">
              "Start trip" streams your location along the route so safety checks run live.
            </p>
          </Card>
        </div>

        {/* Map */}
        <Card title="Map" className="xl:col-span-2">
          <ZoneMap
            geojson={geojson}
            route={trip?.route}
            routeColor={routeColor}
            safetyPoints={trip?.safety?.points || []}
            marker={pos}
            center={pos ? [pos.lat, pos.lon] : undefined}
            zoom={13}
            follow={simulating}
            height={560}
          />
          <p className="mt-2 text-xs text-slate-400">
            Coloured dots show how safe each part of your route is (green = safe, red = risky).
            You only see your safety level — not incident specifics.
          </p>
        </Card>
      </div>

      <AssistantWidget />
    </div>
  );
}

function StatusCard({ status }) {
  if (!status) {
    return (
      <Card title="Current status">
        <div className="flex justify-center py-4"><Spinner /></div>
      </Card>
    );
  }
  const tone = STATUS_TONE[status.status] || STATUS_TONE.no_data;
  const lvl = riskLevel(status.area_risk_score);
  return (
    <Card title="Current status">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {status.status === "safe" ? (
            <ShieldCheck size={18} className="text-emerald-600" />
          ) : (
            <TriangleAlert size={18} className="text-amber-600" />
          )}
          <span className="text-sm font-medium text-slate-700">
            {status.status === "no_data" ? "No location shared yet" : titleCase(status.status)}
          </span>
        </div>
        <Badge className={tone}>{status.status.replace("_", " ")}</Badge>
      </div>

      {status.status !== "no_data" && (
        <div className="mt-4 space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-500">Zone</span>
            <span className="font-medium text-slate-700">{status.zone?.name || "—"}</span>
          </div>
          <div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">Area safety</span>
              <span className="font-semibold" style={{ color: lvl.color }}>{lvl.label}</span>
            </div>
            <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full"
                   style={{ width: `${Math.min(100, (status.area_risk_score || 0) * 100)}%`, backgroundColor: lvl.color }} />
            </div>
          </div>
          {status.on_route != null && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-500">On planned route</span>
              <span className={status.on_route ? "text-emerald-600" : "text-orange-600"}>
                {status.on_route ? "yes" : `off by ${Math.round(status.deviation_m)} m`}
              </span>
            </div>
          )}

          <div>
            <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
              Active warnings
            </div>
            {status.warnings.length === 0 ? (
              <Empty>All clear</Empty>
            ) : (
              <div className="space-y-2">
                {status.warnings.map((w, i) => (
                  <div key={i} className="flex items-start gap-2 text-sm">
                    <Badge className={SEVERITY_STYLES[w.severity] || SEVERITY_STYLES.info}>
                      {w.severity}
                    </Badge>
                    <span className="text-slate-600">{w.reason}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
