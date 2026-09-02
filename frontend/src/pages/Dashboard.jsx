import { useEffect, useState } from "react";
import {
  TriangleAlert,
  BellRing,
  Users,
  Search,
  RefreshCw,
  Newspaper,
  ShieldAlert,
  MapPin,
  Radio,
  ChevronRight,
  Sparkles,
  Layers,
  AlertCircle,
} from "lucide-react";
import { api } from "../lib/api";
import {
  SEVERITY_STYLES,
  RISK_STYLES,
  TOURIST_STATUS_STYLES,
  riskLevel,
  fmtTime,
  titleCase,
} from "../lib/format";
import { Card, StatCard, Badge, Button, Field, Input, Empty, Spinner, ProgressBar } from "../components/ui";
import ZoneMap from "../components/ZoneMap";
import Drawer from "../components/Drawer";
import IncidentDetail from "../components/IncidentDetail";
import TouristDetail from "../components/TouristDetail";

export default function Dashboard() {
  const [geojson, setGeojson] = useState(null);
  const [zones, setZones] = useState([]);
  const [incidents, setIncidents] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [tourists, setTourists] = useState([]);
  const [riskEvents, setRiskEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedTouristId, setSelectedTouristId] = useState(null);
  const [updatedAt, setUpdatedAt] = useState(null);
  const [touristSearch, setTouristSearch] = useState("");

  async function load() {
    try {
      const [gj, zs, inc, al, ts, re] = await Promise.all([
        api.zonesGeojson(),
        api.zones(),
        api.incidents({ limit: 100 }),
        api.alerts({ limit: 50 }),
        api.policeTourists(),
        api.riskEvents({ limit: 50 }),
      ]);
      setGeojson(gj);
      setZones(zs);
      setIncidents(inc);
      setAlerts(al);
      setTourists(ts);
      setRiskEvents(re);
      setUpdatedAt(new Date());
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  const openIncidents = incidents.filter((i) => i.status === "open").length;
  const flagged = tourists.filter((t) => t.status === "panic" || t.status === "alert").length;

  const filteredTourists = tourists.filter((t) =>
    (t.display_name || "Unnamed").toLowerCase().includes(touristSearch.toLowerCase()) ||
    (t.zone_name || "").toLowerCase().includes(touristSearch.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex h-80 flex-col items-center justify-center gap-3 text-slate-500">
        <Spinner size={28} />
        <span className="text-sm font-medium tracking-wide">Syncing Bengaluru Police Command Feed…</span>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Dashboard Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Authority Command Center
            </h1>
            <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700 ring-1 ring-inset ring-blue-600/20">
              Live Monitor
            </span>
          </div>
          <p className="text-sm text-slate-500 mt-0.5">
            Real-time geospatial zones, tourist distress detection, and AI triage intelligence for Bengaluru.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {updatedAt && (
            <span className="text-xs text-slate-400 font-mono">
              Auto-sync: {updatedAt.toLocaleTimeString()}
            </span>
          )}
          <Button variant="ghost" onClick={load} className="shadow-2xs">
            <RefreshCw size={14} className="text-slate-500" /> Refresh Data
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 shadow-xs">
          <AlertCircle size={18} className="shrink-0 text-rose-600" />
          <span>{error} — Verify that your backend server is active on port 8000.</span>
        </div>
      )}

      {/* KPI Metric Cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard
          icon={Users}
          label="Active Tourists"
          value={tourists.length}
          tone="brand"
          pulse={tourists.length > 0}
          subtitle="Currently sharing GPS"
        />
        <StatCard
          icon={TriangleAlert}
          label="Distress / Flagged"
          value={flagged}
          tone={flagged > 0 ? "red" : "emerald"}
          pulse={flagged > 0}
          subtitle={flagged > 0 ? "Requires attention" : "All tourists safe"}
        />
        <StatCard
          icon={BellRing}
          label="Open Incidents"
          value={openIncidents}
          tone="amber"
          subtitle="Active safety tickets"
        />
        <StatCard
          icon={Newspaper}
          label="External Threat Signals"
          value={riskEvents.length}
          tone="slate"
          subtitle="RSS / News intelligence"
        />
      </div>

      {/* Main Map + Right Sidebars */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Tactical Map Container */}
        <Card
          title="Bengaluru Tactical Safety Grid"
          subtitle="Active zones, live tourist positions, and flagged distress incidents"
          icon={Layers}
          className="xl:col-span-2 flex flex-col"
          bodyClassName="p-4 flex-1 flex flex-col"
        >
          <div className="relative flex-1 min-h-[500px] rounded-xl overflow-hidden border border-slate-200">
            <ZoneMap
              geojson={geojson}
              incidents={incidents}
              tourists={tourists}
              height="100%"
              fit
              onIncidentClick={setSelectedId}
              onTouristClick={setSelectedTouristId}
            />
          </div>

          {/* Legend Strip */}
          <div className="mt-3.5 flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-slate-100 text-xs">
            <div className="flex flex-wrap items-center gap-3">
              <Legend color="#10b981" label="Low Risk (Safe)" />
              <Legend color="#f59e0b" label="Moderate Risk" />
              <Legend color="#f97316" label="High Risk Alert" dot />
              <Legend color="#ef4444" label="Restricted / Forest" dot />
              <Legend color="#dc2626" label="Active Incident" dot />
            </div>
            <span className="text-slate-400 text-[11px]">Click any marker to inspect</span>
          </div>
        </Card>

        {/* Right Stack: Active Tourists & Area Risk Lookup */}
        <div className="space-y-6">
          {/* Active Tourists Card */}
          <Card
            title="Monitored Tourists"
            subtitle={`${tourists.length} registered in system`}
            icon={Radio}
            action={
              <span className="text-xs font-semibold text-slate-400 font-mono">
                {tourists.length} Active
              </span>
            }
          >
            <div className="space-y-3">
              {/* Search Bar */}
              <div className="relative">
                <Search size={14} className="absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter by name or zone..."
                  value={touristSearch}
                  onChange={(e) => setTouristSearch(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50/70 pl-8 pr-3 py-1.5 text-xs text-slate-800 placeholder:text-slate-400 focus:bg-white focus:border-blue-600 focus:outline-none focus:ring-1 focus:ring-blue-100"
                />
              </div>

              {/* Tourist List */}
              <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                {filteredTourists.length === 0 && (
                  <Empty>No tourists matching filter.</Empty>
                )}
                {filteredTourists.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setSelectedTouristId(t.id)}
                    className="flex w-full items-center justify-between rounded-xl border border-slate-100 p-2.5 text-left transition hover:border-slate-200 hover:bg-slate-50/80 group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-blue-50 text-blue-600 text-xs font-bold font-mono">
                        {(t.display_name || "T").slice(0, 1).toUpperCase()}
                      </div>
                      <div className="min-w-0">
                        <div className="truncate text-xs font-semibold text-slate-800 group-hover:text-blue-600">
                          {t.display_name || "Unnamed Tourist"}
                        </div>
                        <div className="text-[11px] text-slate-400 truncate">
                          {t.zone_name ? `${t.zone_name}` : "Open Grid"}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <Badge className={TOURIST_STATUS_STYLES[t.status]}>{t.status}</Badge>
                      <ChevronRight size={14} className="text-slate-300 group-hover:text-slate-600 transition" />
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </Card>

          {/* Area Risk Fast Lookup */}
          <RiskLookup />

          {/* Seeded Zones Summary */}
          <Card
            title="Monitored Geo-Zones"
            subtitle="Pre-configured high/low safety zones"
            icon={MapPin}
          >
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {zones.map((z) => (
                <div
                  key={z.id}
                  className="flex items-center justify-between rounded-lg bg-slate-50/80 px-3 py-2 border border-slate-100 text-xs"
                >
                  <span className="font-semibold text-slate-700">{z.name}</span>
                  <Badge className={RISK_STYLES[z.risk_category]}>
                    {z.restricted ? "restricted" : z.risk_category}
                  </Badge>
                </div>
              ))}
              {zones.length === 0 && <Empty>No zones configured.</Empty>}
            </div>
          </Card>
        </div>
      </div>

      {/* Incidents & Alerts Split */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {/* Recent Incidents Table */}
        <Card
          title="Real-Time Detection Incidents"
          subtitle="Automated geofence, route deviation, and panic triggers"
          icon={ShieldAlert}
        >
          {incidents.length === 0 ? (
            <Empty>No incidents detected yet.</Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b border-slate-100 text-left uppercase tracking-wider text-slate-400 font-semibold">
                    <th className="pb-2.5">Incident Type</th>
                    <th className="pb-2.5">Status</th>
                    <th className="pb-2.5">Timestamp</th>
                    <th className="pb-2.5 text-right">Inspect</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {incidents.slice(0, 8).map((i) => (
                    <tr
                      key={i.id}
                      onClick={() => setSelectedId(i.id)}
                      className="cursor-pointer transition hover:bg-slate-50/80 group"
                    >
                      <td className="py-2.5 font-semibold text-slate-800 flex items-center gap-2">
                        {i.details?.trigger === "ai_voice_call" ? (
                          <span className="text-emerald-600 font-bold flex items-center gap-1">
                            <span>📞</span> Voice Call
                          </span>
                        ) : (
                          titleCase(i.incident_type)
                        )}
                      </td>
                      <td className="py-2.5">
                        <Badge className="bg-slate-100 text-slate-600 ring-slate-200">
                          {i.status}
                        </Badge>
                      </td>
                      <td className="py-2.5 text-slate-500 font-mono">
                        {fmtTime(i.detected_at)}
                      </td>
                      <td className="py-2.5 text-right text-blue-600 font-semibold group-hover:underline">
                        View &rsaquo;
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        {/* Advisory Alerts Feed */}
        <Card
          title="Advisory Intelligence Alerts"
          subtitle="Grounded recommendations generated by the AI Triage Agent"
          icon={BellRing}
        >
          {alerts.length === 0 ? (
            <Empty>No active advisory alerts.</Empty>
          ) : (
            <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
              {alerts.slice(0, 6).map((a) => (
                <button
                  key={a.id}
                  onClick={() => setSelectedId(a.incident_id)}
                  className="block w-full rounded-xl border border-slate-200/80 p-3 text-left transition hover:border-blue-300 hover:bg-blue-50/30 group"
                >
                  <div className="mb-1.5 flex items-center justify-between">
                    <Badge className={SEVERITY_STYLES[a.severity]}>{a.severity}</Badge>
                    <span className="text-[11px] text-slate-400 font-mono">{fmtTime(a.created_at)}</span>
                  </div>
                  <p className="text-xs font-semibold text-slate-800 group-hover:text-blue-700">
                    {a.summary || "No summary available"}
                  </p>
                  {a.recommended_action && (
                    <p className="mt-1 text-[11px] text-slate-500 truncate">
                      Action: {a.recommended_action.split("\n")[0]}
                    </p>
                  )}
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>

      {/* Risk Events Feed (Police Only) */}
      <Card
        title="External Threat Intelligence Feed (News & Police RSS)"
        subtitle="Extracted and geo-tagged using Groq LLM grounded agents"
        icon={Newspaper}
      >
        {riskEvents.length === 0 ? (
          <Empty>No risk events ingested. Run the Risk Intelligence agent to populate.</Empty>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {riskEvents.slice(0, 6).map((e) => (
              <div
                key={e.id}
                className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-3.5 space-y-1.5 transition hover:bg-white hover:shadow-xs"
              >
                <div className="flex items-center justify-between">
                  <Badge className="bg-slate-200/70 text-slate-700 ring-slate-300">
                    {titleCase(e.event_type)}
                  </Badge>
                  <span className="text-[11px] text-slate-400 font-mono">
                    {Math.round(e.confidence * 100)}% conf · {fmtTime(e.event_time)}
                  </span>
                </div>
                <p className="text-xs font-bold text-slate-800 leading-snug">{e.title}</p>
                {e.description && (
                  <p className="text-xs text-slate-600 line-clamp-2">{e.description}</p>
                )}
                <div className="flex items-center justify-between pt-1 border-t border-slate-200/40 text-[10px] text-slate-400">
                  <span>Source: {e.source}</span>
                  <span>Grounding: Verified</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Slide-over Inspection Drawers */}
      <Drawer
        open={!!selectedId}
        onClose={() => setSelectedId(null)}
        title="Incident Dossier & Briefing"
      >
        {selectedId && <IncidentDetail incidentId={selectedId} />}
      </Drawer>

      <Drawer
        open={!!selectedTouristId}
        onClose={() => setSelectedTouristId(null)}
        title="Tourist Dossier & Activity"
      >
        {selectedTouristId && <TouristDetail touristId={selectedTouristId} />}
      </Drawer>
    </div>
  );
}

function Legend({ color, label, dot }) {
  return (
    <span className="inline-flex items-center gap-1.5 font-medium text-slate-600">
      <span
        className={dot ? "h-2.5 w-2.5 rounded-full" : "h-2.5 w-4 rounded-xs"}
        style={{ backgroundColor: color }}
      />
      {label}
    </span>
  );
}

function RiskLookup() {
  const [lat, setLat] = useState("12.9770");
  const [lon, setLon] = useState("77.5720");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  async function lookup() {
    setBusy(true);
    setErr(null);
    try {
      const [risk, zone] = await Promise.all([
        api.areaRisk(Number(lat), Number(lon)),
        api.zoneAt(Number(lat), Number(lon)),
      ]);
      setResult({ score: risk.risk_score, zone: zone.zone });
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  const lvl = result ? riskLevel(result.score) : null;

  return (
    <Card
      title="Area Risk Query"
      subtitle="Point-in-time spatiotemporal risk lookup"
      icon={Search}
    >
      <div className="grid grid-cols-2 gap-2">
        <Field label="Latitude">
          <Input value={lat} onChange={(e) => setLat(e.target.value)} />
        </Field>
        <Field label="Longitude">
          <Input value={lon} onChange={(e) => setLon(e.target.value)} />
        </Field>
      </div>
      <Button className="mt-3 w-full bg-slate-800 hover:bg-slate-900 text-white" onClick={lookup} disabled={busy}>
        {busy ? <Spinner /> : <Search size={14} />} Calculate Risk Probability
      </Button>
      {err && <p className="mt-2 text-xs text-rose-600">{err}</p>}
      {result && (
        <div className="mt-3 rounded-lg bg-slate-50 p-3 border border-slate-200 text-xs space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-500">Predicted Risk:</span>
            <span className="font-bold" style={{ color: lvl.color }}>
              {result.score == null ? "n/a" : result.score.toFixed(3)} · {lvl.label}
            </span>
          </div>
          <ProgressBar value={Math.round((result.score || 0) * 100)} max={100} color={lvl.color} height={6} />
          <div className="text-slate-500 pt-1">
            Zone: <strong className="text-slate-800">{result.zone ? result.zone.name : "Unzoned Grid"}</strong>
          </div>
        </div>
      )}
    </Card>
  );
}
