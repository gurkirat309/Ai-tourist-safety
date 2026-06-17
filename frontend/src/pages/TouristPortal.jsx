import { useEffect, useState } from "react";
import { UserPlus, Navigation, Siren, LocateFixed, RotateCcw } from "lucide-react";
import { api } from "../lib/api";
import { SEVERITY_STYLES, riskLevel, titleCase } from "../lib/format";
import { Card, Badge, Button, Field, Input, Spinner } from "../components/ui";
import ZoneMap from "../components/ZoneMap";

export default function TouristPortal() {
  const [tourist, setTourist] = useState(null);
  const [geojson, setGeojson] = useState(null);

  useEffect(() => {
    api.zonesGeojson().then(setGeojson).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-800">Tourist Portal</h1>
        <p className="text-sm text-slate-500">
          Register with consent, share your location, and raise a panic alert.
        </p>
      </div>

      {!tourist ? (
        <RegisterCard onRegistered={setTourist} />
      ) : (
        <ActiveTourist tourist={tourist} geojson={geojson} onReset={() => setTourist(null)} />
      )}
    </div>
  );
}

function RegisterCard({ onRegistered }) {
  const [form, setForm] = useState({
    display_name: "",
    nationality: "",
    emergency_contact: "",
    consent: true,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const t = await api.registerTourist({
        display_name: form.display_name || null,
        nationality: form.nationality || null,
        emergency_contact: form.emergency_contact || null,
        consent: { consent_given: form.consent, consent_purpose: "safety_monitoring" },
      });
      onRegistered(t);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="Register a tourist" className="max-w-xl">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Name">
          <Input value={form.display_name} onChange={set("display_name")} placeholder="Aarav Sharma" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Nationality">
            <Input value={form.nationality} onChange={set("nationality")} placeholder="IN" />
          </Field>
          <Field label="Emergency contact">
            <Input value={form.emergency_contact} onChange={set("emergency_contact")} placeholder="+91-…" />
          </Field>
        </div>
        <label className="flex items-start gap-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={form.consent}
            onChange={(e) => setForm({ ...form, consent: e.target.checked })}
            className="mt-0.5 h-4 w-4 accent-brand-600"
          />
          <span>
            I consent to processing my location for <b>safety monitoring</b> (DPDP).
            Location data has a retention window and is minimized after expiry.
          </span>
        </label>
        {err && <p className="text-sm text-red-600">{err}</p>}
        <Button type="submit" disabled={busy}>
          {busy ? <Spinner /> : <UserPlus size={16} />} Register
        </Button>
      </form>
    </Card>
  );
}

function ActiveTourist({ tourist, geojson, onReset }) {
  const [lat, setLat] = useState("12.8000");
  const [lon, setLon] = useState("77.5770");
  const [busy, setBusy] = useState(null);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState(null);

  function useMyLocation() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((pos) => {
      setLat(pos.coords.latitude.toFixed(5));
      setLon(pos.coords.longitude.toFixed(5));
    });
  }

  async function act(kind) {
    setBusy(kind);
    setErr(null);
    try {
      const body = { location: { lat: Number(lat), lon: Number(lon) } };
      const res =
        kind === "panic"
          ? await api.panic(tourist.id, body)
          : await api.ingestPing(tourist.id, body);
      setResult(res);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  }

  const lvl = result ? riskLevel(result.area_risk_score) : null;

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <div className="space-y-6">
        <Card
          title="Active tourist"
          action={
            <Button variant="ghost" onClick={onReset} className="!px-3 !py-1 text-xs">
              <RotateCcw size={14} /> New
            </Button>
          }
        >
          <div className="text-sm text-slate-700">
            <div className="font-semibold">{tourist.display_name || "Unnamed"}</div>
            <div className="text-slate-500">
              {tourist.nationality || "—"} · consent:{" "}
              {tourist.consent_given ? (
                <span className="text-emerald-600">given</span>
              ) : (
                <span className="text-red-600">none</span>
              )}
            </div>
            <div className="mt-1 font-mono text-xs text-slate-400">{tourist.id}</div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3">
            <Field label="Latitude">
              <Input value={lat} onChange={(e) => setLat(e.target.value)} />
            </Field>
            <Field label="Longitude">
              <Input value={lon} onChange={(e) => setLon(e.target.value)} />
            </Field>
          </div>
          <Button variant="ghost" onClick={useMyLocation} className="mt-2 w-full">
            <LocateFixed size={16} /> Use my location
          </Button>

          <div className="mt-3 grid grid-cols-2 gap-3">
            <Button onClick={() => act("ping")} disabled={busy}>
              {busy === "ping" ? <Spinner /> : <Navigation size={16} />} Share location
            </Button>
            <Button variant="danger" onClick={() => act("panic")} disabled={busy}>
              {busy === "panic" ? <Spinner /> : <Siren size={16} />} Panic
            </Button>
          </div>
          {err && <p className="mt-2 text-sm text-red-600">{err}</p>}
        </Card>

        {result && <ResultCard result={result} lvl={lvl} />}
      </div>

      <Card title="Your location & zones">
        <ZoneMap
          geojson={geojson}
          marker={{ lat: Number(lat), lon: Number(lon), label: tourist.display_name }}
          center={[Number(lat), Number(lon)]}
          zoom={13}
          height={520}
        />
      </Card>
    </div>
  );
}

function ResultCard({ result, lvl }) {
  return (
    <Card title="Latest assessment">
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-500">Zone</span>
        <span className="text-sm font-medium text-slate-700">{result.zone_name || "—"}</span>
      </div>

      <div className="mt-3">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-500">Area-risk score</span>
          <span className="font-semibold" style={{ color: lvl.color }}>
            {result.area_risk_score == null ? "n/a" : result.area_risk_score.toFixed(3)} · {lvl.label}
          </span>
        </div>
        <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full"
            style={{
              width: `${Math.min(100, (result.area_risk_score || 0) * 100)}%`,
              backgroundColor: lvl.color,
            }}
          />
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <span className="text-sm text-slate-500">Escalation</span>
        {result.escalation ? (
          <Badge className={SEVERITY_STYLES[result.escalation]}>{result.escalation}</Badge>
        ) : (
          <span className="text-sm text-emerald-600">all clear</span>
        )}
      </div>

      {result.signals?.length > 0 && (
        <div className="mt-4">
          <div className="mb-1 text-xs font-medium uppercase tracking-wide text-slate-400">
            Detection signals
          </div>
          <div className="space-y-2">
            {result.signals.map((s, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <Badge className={SEVERITY_STYLES[s.severity] || SEVERITY_STYLES.info}>
                  {s.severity}
                </Badge>
                <span className="text-slate-600">{s.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {result.incident_id && (
        <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-500">
          {result.incident_created ? "Incident created" : "Incident updated"} ·{" "}
          <span className="font-mono">{result.incident_id.slice(0, 8)}</span>
        </div>
      )}
    </Card>
  );
}
