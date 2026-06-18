import { useEffect, useState } from "react";
import {
  TriangleAlert,
  BellRing,
  Users,
  Search,
  RefreshCw,
  Newspaper,
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
import { Card, StatCard, Badge, Button, Field, Input, Empty, Spinner } from "../components/ui";
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

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center gap-3 text-slate-500">
        <Spinner /> Loading control center…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-800">Police Dashboard</h1>
          <p className="text-sm text-slate-500">
            Live zones, incidents, and advisory alerts for Bengaluru.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {updatedAt && (
            <span className="text-xs text-slate-400">
              Updated {updatedAt.toLocaleTimeString()}
            </span>
          )}
          <Button variant="ghost" onClick={load}>
            <RefreshCw size={16} /> Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error} — is the backend running on :8000?
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard icon={Users} label="Tourists tracked" value={tourists.length} tone="brand" />
        <StatCard icon={TriangleAlert} label="Flagged tourists" value={flagged} tone="red" />
        <StatCard icon={BellRing} label="Open incidents" value={openIncidents} tone="amber" />
        <StatCard icon={Newspaper} label="Risk events" value={riskEvents.length} tone="slate" />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card title="Live map" className="xl:col-span-2">
          <ZoneMap
            geojson={geojson}
            incidents={incidents}
            tourists={tourists}
            height={460}
            fit
            onIncidentClick={setSelectedId}
            onTouristClick={setSelectedTouristId}
          />
          <div className="mt-3 flex flex-wrap gap-3 text-xs text-slate-500">
            <Legend color="#10b981" label="Low/Safe" />
            <Legend color="#f59e0b" label="Moderate" />
            <Legend color="#f97316" label="High/Alert" dot />
            <Legend color="#ef4444" label="Restricted/Panic" dot />
            <Legend color="#dc2626" label="Incident" dot />
          </div>
        </Card>

        <div className="space-y-6">
          <Card title="Active tourists">
            <div className="space-y-2">
              {tourists.length === 0 && <Empty>No tourists yet.</Empty>}
              {tourists.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setSelectedTouristId(t.id)}
                  className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left transition hover:bg-slate-50"
                >
                  <span className="truncate text-sm text-slate-700">
                    {t.display_name || "Unnamed"}
                    {t.zone_name ? <span className="text-slate-400"> · {t.zone_name}</span> : ""}
                  </span>
                  <Badge className={TOURIST_STATUS_STYLES[t.status]}>{t.status}</Badge>
                </button>
              ))}
            </div>
          </Card>
          <RiskLookup />
          <Card title="Zones">
            <div className="space-y-2">
              {zones.map((z) => (
                <div key={z.id} className="flex items-center justify-between">
                  <span className="text-sm text-slate-700">{z.name}</span>
                  <Badge className={RISK_STYLES[z.risk_category]}>
                    {z.restricted ? "restricted" : z.risk_category}
                  </Badge>
                </div>
              ))}
              {zones.length === 0 && <Empty>No zones seeded.</Empty>}
            </div>
          </Card>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card title="Recent incidents">
          {incidents.length === 0 ? (
            <Empty>No incidents yet.</Empty>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-slate-400">
                  <tr>
                    <th className="pb-2">Type</th>
                    <th className="pb-2">Status</th>
                    <th className="pb-2">Detected</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {incidents.slice(0, 8).map((i) => (
                    <tr
                      key={i.id}
                      onClick={() => setSelectedId(i.id)}
                      className="cursor-pointer transition hover:bg-slate-50"
                    >
                      <td className="py-2 font-medium text-slate-700">
                        {titleCase(i.incident_type)}
                      </td>
                      <td className="py-2">
                        <Badge className="bg-slate-100 text-slate-600 ring-slate-200">
                          {i.status}
                        </Badge>
                      </td>
                      <td className="py-2 text-slate-500">{fmtTime(i.detected_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Recent alerts">
          {alerts.length === 0 ? (
            <Empty>No alerts yet.</Empty>
          ) : (
            <div className="space-y-3">
              {alerts.slice(0, 6).map((a) => (
                <button
                  key={a.id}
                  onClick={() => setSelectedId(a.incident_id)}
                  className="block w-full rounded-lg border border-slate-100 p-3 text-left transition hover:border-slate-200 hover:bg-slate-50"
                >
                  <div className="mb-1 flex items-center justify-between">
                    <Badge className={SEVERITY_STYLES[a.severity]}>{a.severity}</Badge>
                    <span className="text-xs text-slate-400">{fmtTime(a.created_at)}</span>
                  </div>
                  <p className="text-sm text-slate-700">{a.summary || "—"}</p>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>

      <Card title="Risk events (crime & hazards) — police only">
        {riskEvents.length === 0 ? (
          <Empty>No risk events. Run the Risk Intelligence agent to populate.</Empty>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {riskEvents.slice(0, 8).map((e) => (
              <div key={e.id} className="rounded-lg border border-slate-100 p-3">
                <div className="mb-1 flex items-center justify-between">
                  <Badge className="bg-slate-100 text-slate-600 ring-slate-200">
                    {titleCase(e.event_type)}
                  </Badge>
                  <span className="text-xs text-slate-400">
                    {Math.round(e.confidence * 100)}% · {fmtTime(e.event_time)}
                  </span>
                </div>
                <p className="text-sm font-medium text-slate-700">{e.title}</p>
                {e.description && (
                  <p className="mt-0.5 text-xs text-slate-500">{e.description}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Drawer
        open={!!selectedId}
        onClose={() => setSelectedId(null)}
        title="Incident detail"
      >
        {selectedId && <IncidentDetail incidentId={selectedId} />}
      </Drawer>

      <Drawer
        open={!!selectedTouristId}
        onClose={() => setSelectedTouristId(null)}
        title="Tourist detail"
      >
        {selectedTouristId && <TouristDetail touristId={selectedTouristId} />}
      </Drawer>
    </div>
  );
}

function Legend({ color, label, dot }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        className={dot ? "h-2.5 w-2.5 rounded-full" : "h-2.5 w-4 rounded-sm"}
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
    <Card title="Area-risk lookup">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Latitude">
          <Input value={lat} onChange={(e) => setLat(e.target.value)} />
        </Field>
        <Field label="Longitude">
          <Input value={lon} onChange={(e) => setLon(e.target.value)} />
        </Field>
      </div>
      <Button className="mt-3 w-full" onClick={lookup} disabled={busy}>
        {busy ? <Spinner /> : <Search size={16} />} Check risk
      </Button>
      {err && <p className="mt-2 text-xs text-red-600">{err}</p>}
      {result && (
        <div className="mt-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-slate-500">Risk score</span>
            <span className="font-semibold" style={{ color: lvl.color }}>
              {result.score == null ? "n/a" : result.score.toFixed(3)} · {lvl.label}
            </span>
          </div>
          <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full"
              style={{
                width: `${Math.min(100, (result.score || 0) * 100)}%`,
                backgroundColor: lvl.color,
              }}
            />
          </div>
          <div className="mt-2 text-xs text-slate-500">
            Zone: {result.zone ? result.zone.name : "none"}
          </div>
        </div>
      )}
    </Card>
  );
}
