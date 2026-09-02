import { useEffect, useRef, useState } from "react";
import {
  Siren,
  Route as RouteIcon,
  Play,
  Square,
  ShieldCheck,
  TriangleAlert,
  PhoneCall,
  MapPin,
  Compass,
  Navigation,
  Sparkles,
  Info,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import { api } from "../lib/api";
import { SEVERITY_STYLES, riskLevel, titleCase } from "../lib/format";
import { Card, Badge, Button, Spinner, Empty, ProgressBar } from "../components/ui";
import ZoneMap from "../components/ZoneMap";
import PlacePicker from "../components/PlacePicker";
import AssistantWidget from "../components/AssistantWidget";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const STATUS_CONFIG = {
  safe: {
    bg: "bg-emerald-50 border-emerald-200 text-emerald-800",
    badge: "bg-emerald-100 text-emerald-800 ring-emerald-300",
    dot: "bg-emerald-500",
    icon: ShieldCheck,
    title: "Safe Corridor Active",
  },
  warning: {
    bg: "bg-amber-50 border-amber-200 text-amber-900",
    badge: "bg-amber-100 text-amber-800 ring-amber-300",
    dot: "bg-amber-500",
    icon: TriangleAlert,
    title: "Caution Advised",
  },
  critical: {
    bg: "bg-rose-50 border-rose-200 text-rose-900",
    badge: "bg-rose-100 text-rose-800 ring-rose-300",
    dot: "bg-rose-500",
    icon: Siren,
    title: "High Alert / SOS Triggered",
  },
  no_data: {
    bg: "bg-slate-50 border-slate-200 text-slate-700",
    badge: "bg-slate-100 text-slate-600 ring-slate-200",
    dot: "bg-slate-400",
    icon: Navigation,
    title: "Standby — Share Location",
  },
};

export default function TouristPortal() {
  const [geojson, setGeojson] = useState(null);
  const [status, setStatus] = useState(null);
  const [trip, setTrip] = useState(null);
  const [places, setPlaces] = useState([]);
  const [start, setStart] = useState(null);
  const [dest, setDest] = useState(null);
  const [pos, setPos] = useState(null);
  const [busy, setBusy] = useState(null);
  const [deviate, setDeviate] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [phone, setPhone] = useState(() => localStorage.getItem("ts_phone") || "");
  const [callMsg, setCallMsg] = useState(null);
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
      setErr("Please select both a starting point and a destination first.");
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

  async function callAI() {
    if (!phone || phone.trim().length < 8) {
      setErr("Please enter a valid phone number (e.g. +91 9876543210) to receive the AI call.");
      return;
    }
    setBusy("call");
    setErr(null);
    setCallMsg(null);
    try {
      localStorage.setItem("ts_phone", phone.trim());
      const res = await api.requestVoiceCall({ phone_number: phone.trim() });
      setCallMsg(`Dialing ${res.phone}... Pick up your phone when it rings!`);
      await loadStatus();
    } catch (e) {
      setErr(e.message || "Failed to initiate AI call.");
    } finally {
      setBusy(null);
    }
  }

  async function simulate() {
    if (!trip?.route?.length) return;
    setSimulating(true);
    stopRef.current = false;
    setErr(null);
    const pts = trip.route;
    const step = Math.max(1, Math.floor(pts.length / 12));
    const sampled = pts.filter((_, i) => i % step === 0);
    try {
      for (let i = 0; i < sampled.length; i++) {
        if (stopRef.current) break;
        let [lat, lon] = sampled[i];
        if (deviate && i > sampled.length / 2) {
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

  const quickPicks = places.filter((p) =>
    ["Cubbon Park", "Lalbagh Botanical Garden", "Bangalore Palace", "Bannerghatta National Park", "MG Road"].includes(p.name)
  );

  const routeColor = trip ? riskLevel(trip.safety.max_score).color : "#2563eb";

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Banner Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-2xl bg-gradient-to-r from-slate-900 via-blue-950 to-slate-900 p-6 text-white shadow-sm border border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/20 px-2.5 py-0.5 text-xs font-semibold text-blue-300 ring-1 ring-inset ring-blue-400/30">
              <Sparkles size={12} /> Live Protection Shield
            </span>
          </div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
            Travel Safety Companion
          </h1>
          <p className="text-xs sm:text-sm text-slate-300 mt-1 max-w-xl">
            Real-time GPS monitoring, spatiotemporal route risk evaluation, and instant two-way AI voice assistance across Bengaluru.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="bg-slate-800/80 rounded-xl p-3 border border-slate-700/60 text-right">
            <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Active Monitoring</div>
            <div className="text-sm font-bold text-emerald-400 flex items-center justify-end gap-1.5 mt-0.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              Bengaluru Safe Net
            </div>
          </div>
        </div>
      </div>

      {err && (
        <div className="flex items-center gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 shadow-xs">
          <AlertTriangle size={18} className="shrink-0 text-rose-600" />
          <span>{err}</span>
        </div>
      )}

      {/* Main Grid: Controls Left, Tactical Map Right */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Left Column Controls */}
        <div className="space-y-6 xl:col-span-1">
          {/* Current Status Card */}
          <StatusCard status={status} />

          {/* Plan a Trip Card */}
          <Card
            title="Journey Route Planner"
            subtitle="Choose your starting point and destination"
            icon={Compass}
          >
            <div className="space-y-4">
              {/* Journey Step Line */}
              <div className="relative pl-6 space-y-4">
                {/* Connecting vertical line */}
                <div className="absolute left-2.5 top-3 bottom-3 w-0.5 bg-slate-200 border-l border-dashed border-slate-300" />

                {/* Start Step */}
                <div className="relative">
                  <div className="absolute -left-6 top-2 h-3.5 w-3.5 rounded-full border-2 border-emerald-500 bg-white ring-2 ring-emerald-100" />
                  <PlacePicker
                    label="Origin (Start Location)"
                    value={start}
                    onChange={setStart}
                    curated={places}
                    allowMyLocation
                    placeholder="Where are you now?"
                  />
                </div>

                {/* Destination Step */}
                <div className="relative">
                  <div className="absolute -left-6 top-2 h-3.5 w-3.5 rounded-full border-2 border-rose-500 bg-white ring-2 ring-rose-100" />
                  <PlacePicker
                    label="Destination"
                    value={dest}
                    onChange={setDest}
                    curated={places}
                    placeholder="Where are you heading?"
                  />
                </div>
              </div>

              {/* Quick Destination Chips */}
              {quickPicks.length > 0 && (
                <div>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Popular Bengaluru Spots
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {quickPicks.map((p) => (
                      <button
                        key={p.name}
                        onClick={() => setDest({ name: p.name, lat: p.lat, lon: p.lon })}
                        className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50/80 px-2.5 py-1 text-xs font-medium text-slate-700 transition hover:border-blue-300 hover:bg-blue-50/60 hover:text-blue-700"
                      >
                        <MapPin size={11} className="text-slate-400" />
                        {p.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              <Button
                onClick={planTrip}
                disabled={busy === "plan"}
                className="w-full bg-blue-600 hover:bg-blue-700 py-2.5 shadow-sm"
              >
                {busy === "plan" ? <Spinner /> : <RouteIcon size={16} />} Analyze & Plan Safe Route
              </Button>

              {/* Trip Analysis Summary */}
              {trip && (
                <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                      Evaluated Route Safety
                    </span>
                    <Badge
                      className="px-2.5 py-0.5 text-xs font-bold"
                      style={{
                        backgroundColor: `${routeColor}15`,
                        color: routeColor,
                        borderColor: `${routeColor}40`,
                      }}
                    >
                      {trip.safety.label}
                    </Badge>
                  </div>
                  <div className="flex items-center justify-between text-xs text-slate-600 pt-1 border-t border-slate-200/60">
                    <span>Distance: <strong className="text-slate-800">{(trip.distance_m / 1000).toFixed(1)} km</strong></span>
                    <span>Est. Time: <strong className="text-slate-800">~{Math.round(trip.duration_s / 60)} mins</strong></span>
                    <span className="text-[10px] text-slate-400">OSRM Engine</span>
                  </div>
                </div>
              )}
            </div>
          </Card>

          {/* Travel & Emergency Action Console */}
          <Card
            title="Travel & Emergency Actions"
            subtitle="Active controls during your trip"
            icon={Siren}
          >
            <div className="space-y-4">
              {/* Trip Simulation Controls */}
              <div className="rounded-xl bg-slate-50 p-3.5 border border-slate-200/60">
                <div className="flex items-center justify-between mb-2.5">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-600">
                    Trip Streaming Simulation
                  </span>
                  <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={deviate}
                      onChange={(e) => setDeviate(e.target.checked)}
                      className="h-3.5 w-3.5 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span>Test off-route</span>
                  </label>
                </div>
                {!simulating ? (
                  <Button
                    onClick={simulate}
                    disabled={!trip}
                    className="w-full bg-slate-800 hover:bg-slate-900 text-white"
                  >
                    <Play size={15} /> Start Live Trip Streaming
                  </Button>
                ) : (
                  <Button
                    variant="ghost"
                    onClick={() => (stopRef.current = true)}
                    className="w-full border-rose-300 text-rose-700 hover:bg-rose-50"
                  >
                    <Square size={15} /> Stop Location Streaming
                  </Button>
                )}
              </div>

              {/* Emergency Action Split */}
              <div className="space-y-3 pt-1">
                {/* Two-Way AI Voice Call Button */}
                <div className="rounded-xl border border-emerald-200/90 bg-emerald-50/40 p-3.5 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-emerald-800">
                      <PhoneCall size={14} className="text-emerald-600" />
                      <span>Two-Way AI Voice Call</span>
                    </div>
                    <span className="text-[10px] font-semibold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full">
                      Instant Dial
                    </span>
                  </div>

                  <input
                    type="tel"
                    placeholder="Enter phone: e.g. +919876543210"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-800 placeholder:text-slate-400 focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-100"
                  />

                  <Button
                    onClick={callAI}
                    disabled={busy === "call"}
                    className="w-full bg-emerald-600 hover:bg-emerald-700 text-white py-2.5 shadow-xs font-semibold"
                  >
                    {busy === "call" ? <Spinner /> : <PhoneCall size={16} />} Call AI Safety Assistant
                  </Button>

                  {callMsg && (
                    <div className="rounded-lg bg-emerald-100/80 border border-emerald-300 p-2.5 text-xs text-emerald-900 flex items-center gap-2 animate-pulse">
                      <CheckCircle2 size={16} className="text-emerald-700 shrink-0" />
                      <span>{callMsg}</span>
                    </div>
                  )}
                </div>

                {/* Panic SOS Button */}
                <Button
                  variant="danger"
                  onClick={panic}
                  disabled={busy === "panic"}
                  className="w-full py-3 text-base font-bold tracking-tight shadow-md shadow-rose-600/20"
                >
                  {busy === "panic" ? <Spinner /> : <Siren size={18} />} Emergency Panic SOS
                </Button>
              </div>
            </div>
          </Card>
        </div>

        {/* Right Tactical Map */}
        <Card
          title="Bengaluru Live Safety Map"
          subtitle="Real-time geo-fencing, route safety dots, and risk zone monitoring"
          icon={Navigation}
          className="xl:col-span-2 flex flex-col"
          bodyClassName="p-4 flex-1 flex flex-col"
        >
          <div className="relative flex-1 min-h-[500px] rounded-xl overflow-hidden border border-slate-200">
            <ZoneMap
              geojson={geojson}
              route={trip?.route}
              routeColor={routeColor}
              safetyPoints={trip?.safety?.points || []}
              marker={pos}
              center={pos ? [pos.lat, pos.lon] : undefined}
              zoom={13}
              follow={simulating}
              height="100%"
            />
          </div>

          {/* Floating Map Legend Bar */}
          <div className="mt-3.5 flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100 text-xs">
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-semibold text-slate-500 uppercase tracking-wider text-[11px]">Safety Zones:</span>
              <span className="inline-flex items-center gap-1.5 text-slate-600 font-medium">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> Low Risk
              </span>
              <span className="inline-flex items-center gap-1.5 text-slate-600 font-medium">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500" /> Moderate
              </span>
              <span className="inline-flex items-center gap-1.5 text-slate-600 font-medium">
                <span className="h-2.5 w-2.5 rounded-full bg-orange-500" /> High Alert
              </span>
              <span className="inline-flex items-center gap-1.5 text-slate-600 font-medium">
                <span className="h-2.5 w-2.5 rounded-full bg-rose-500" /> Restricted Forest
              </span>
            </div>
            <div className="text-slate-400 text-[11px]">
              OpenStreetMap · PostGIS Spatial Engine
            </div>
          </div>
        </Card>
      </div>

      <AssistantWidget />
    </div>
  );
}

function StatusCard({ status }) {
  if (!status) {
    return (
      <Card title="Safety Status Radar" icon={ShieldCheck}>
        <div className="flex justify-center py-6">
          <Spinner size={24} />
        </div>
      </Card>
    );
  }

  const cfg = STATUS_CONFIG[status.status] || STATUS_CONFIG.no_data;
  const Icon = cfg.icon;
  const lvl = riskLevel(status.area_risk_score);
  const safetyPercentage = Math.round(Math.max(0, (1 - (status.area_risk_score || 0.1)) * 100));

  return (
    <Card
      title="Safety Status Radar"
      subtitle="Real-time sensor & area evaluation"
      icon={ShieldCheck}
    >
      <div className={`rounded-xl border p-4 transition-all ${cfg.bg}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="grid h-9 w-9 place-items-center rounded-lg bg-white/80 shadow-xs">
              <Icon size={20} className="shrink-0" />
            </div>
            <div>
              <div className="text-sm font-bold leading-tight">{cfg.title}</div>
              <div className="text-xs opacity-75">
                {status.status === "no_data" ? "No GPS reported yet" : "Autonomous Guardian Active"}
              </div>
            </div>
          </div>
          <Badge className={cfg.badge} dot dotColor={cfg.dot}>
            {status.status.replace("_", " ")}
          </Badge>
        </div>

        {status.status !== "no_data" && (
          <div className="mt-4 space-y-3 pt-3 border-t border-black/5">
            {/* Area Safety Gauge Bar */}
            <div>
              <div className="flex items-center justify-between text-xs font-semibold mb-1">
                <span>Safe Corridor Rating</span>
                <span style={{ color: lvl.color }}>{safetyPercentage}% ({lvl.label})</span>
              </div>
              <ProgressBar value={safetyPercentage} max={100} color={lvl.color} height={7} />
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs pt-1">
              <div className="rounded-lg bg-white/60 p-2 border border-black/5">
                <span className="text-slate-500 block text-[10px] uppercase font-bold tracking-wider">Current Zone</span>
                <span className="font-bold text-slate-800 truncate block mt-0.5">
                  {status.zone?.name || "Open Bengaluru Grid"}
                </span>
              </div>
              <div className="rounded-lg bg-white/60 p-2 border border-black/5">
                <span className="text-slate-500 block text-[10px] uppercase font-bold tracking-wider">Route Deviation</span>
                <span className={`font-bold block mt-0.5 ${status.on_route ? "text-emerald-700" : "text-amber-700"}`}>
                  {status.on_route != null ? (status.on_route ? "On Route" : `Off by ${Math.round(status.deviation_m)}m`) : "—"}
                </span>
              </div>
            </div>

            {/* Active Warnings Feed */}
            {status.warnings && status.warnings.length > 0 && (
              <div className="space-y-1.5 pt-1">
                <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Active Safety Signals
                </div>
                {status.warnings.map((w, i) => (
                  <div key={i} className="flex items-center gap-2 rounded-md bg-white/90 p-1.5 text-xs shadow-2xs border border-black/5">
                    <Badge className={SEVERITY_STYLES[w.severity] || SEVERITY_STYLES.info}>
                      {w.severity}
                    </Badge>
                    <span className="text-slate-700 truncate">{w.reason}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
