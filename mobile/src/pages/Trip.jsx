/**
 * Trip planning: pick start + destination, get a route scored for safety,
 * and register it as the planned route the deviation detector checks against.
 */
import { useEffect, useState } from "react";
import {
  Route as RouteIcon,
  ShieldCheck,
  TriangleAlert,
  Clock,
  Ruler,
  PlayCircle,
  Info,
} from "lucide-react";
import { api } from "../lib/api";
import { useTracking } from "../lib/tracking";
import { riskLevel, fmtDistance, fmtDuration, titleCase } from "../lib/format";
import { Card, Button, Banner, Meter, Chip } from "../components/ui";
import PlacePicker from "../components/PlacePicker";
import MiniMap from "../components/MiniMap";
import RouteOptions from "../components/RouteOptions";
import RiskForecast from "../components/RiskForecast";

export default function Trip() {
  const { startDemo, tracking, stop, status } = useTracking();

  const [places, setPlaces] = useState([]);
  const [geojson, setGeojson] = useState(null);
  const [start, setStart] = useState(null);
  const [dest, setDest] = useState(null);
  const [trip, setTrip] = useState(null);
  const [busy, setBusy] = useState(null);
  const [err, setErr] = useState(null);
  const [deviate, setDeviate] = useState(false);

  useEffect(() => {
    api.places().then((d) => setPlaces(d.places || [])).catch(() => {});
    api.zonesGeojson().then(setGeojson).catch(() => {});
  }, []);

  async function plan(prefer = "safest") {
    if (!start || !dest) {
      setErr("Choose both a starting point and a destination.");
      return;
    }
    setBusy("plan");
    setErr(null);
    try {
      const t = await api.planTrip({
        start: { lat: Number(start.lat), lon: Number(start.lon) },
        destination: { lat: Number(dest.lat), lon: Number(dest.lon) },
        prefer,
      });
      setTrip(t);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  }

  async function runDemo() {
    if (!trip?.route?.length) return;
    if (tracking) stop();
    setErr(null);
    await startDemo(trip.route, { deviate });
  }

  const risk = trip ? riskLevel(trip.safety?.max_score) : null;

  return (
    <div className="space-y-3.5 p-4">
      {err && (
        <Banner tone="rose" icon={TriangleAlert}>
          {err}
        </Banner>
      )}

      <Card className="space-y-4 p-4">
        <div className="flex items-center gap-2">
          <RouteIcon size={16} className="text-blue-600" />
          <h2 className="text-[14px] font-bold text-slate-900">Plan a trip</h2>
        </div>

        <PlacePicker
          label="Starting from"
          value={start}
          onChange={setStart}
          places={places}
          allowCurrent
        />
        <PlacePicker
          label="Going to"
          value={dest}
          onChange={setDest}
          places={places}
        />

        <Button
          full
          icon={RouteIcon}
          busy={busy === "plan"}
          onClick={() => plan("safest")}
        >
          Check route safety
        </Button>

        <p className="text-[11px] leading-relaxed text-slate-500">
          Planning a trip also tells the system your intended route, so it can
          notice if you drift far from it.
        </p>
      </Card>

      {trip && (
        <>
          <RouteOptions
            trip={trip}
            busy={busy === "plan"}
            onSelect={(prefer) => plan(prefer)}
          />

          <Card className="overflow-hidden">
            <div className="px-4 pt-4">
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {trip.safety?.max_score != null && trip.safety.max_score >= 0.3 ? (
                    <TriangleAlert size={16} className="text-amber-600" />
                  ) : (
                    <ShieldCheck size={16} className="text-emerald-600" />
                  )}
                  <h3 className="text-[14px] font-bold text-slate-900">
                    Route safety
                  </h3>
                </div>
                {risk && (
                  <Chip className="bg-slate-100 uppercase">
                    <span style={{ color: risk.color }}>
                      {trip.safety?.label || risk.label}
                    </span>
                  </Chip>
                )}
              </div>

              {trip.safety?.max_score != null && (
                <>
                  <Meter value={trip.safety.max_score} color={risk.color} />
                  <p className="mt-1.5 text-[11px] text-slate-500">
                    Riskiest point on this route scores{" "}
                    {trip.safety.max_score.toFixed(2)}
                    {trip.safety.overall_score != null &&
                      ` · average ${trip.safety.overall_score.toFixed(2)}`}
                  </p>
                </>
              )}
            </div>

            <div className="mt-3 grid grid-cols-3 divide-x divide-slate-100 border-t border-slate-100">
              <Stat icon={Ruler} label="Distance" value={fmtDistance(trip.distance_m)} />
              <Stat icon={Clock} label="Duration" value={fmtDuration(trip.duration_s)} />
              <Stat
                icon={Info}
                label="Source"
                value={trip.source === "osrm" ? "Road" : "Direct"}
              />
            </div>
          </Card>

          <Card className="overflow-hidden">
            <MiniMap
              className="h-64"
              geojson={geojson}
              route={trip.route}
              routeColor={risk?.color || "#2563eb"}
              safetyPoints={trip.safety?.points || []}
              position={status?.last_position}
              fit={false}
              zoom={12}
              resizeKey={trip.route?.length}
            />
          </Card>

          {dest && (
            <RiskForecast
              lat={Number(dest.lat)}
              lon={Number(dest.lon)}
              title={`Risk at ${dest.name}`}
            />
          )}

          <Card className="space-y-3 p-4">
            <div className="flex items-center gap-2">
              <PlayCircle size={16} className="text-violet-600" />
              <h3 className="text-[14px] font-bold text-slate-900">Demo mode</h3>
            </div>
            <p className="text-[12px] leading-relaxed text-slate-600">
              Replays this route as simulated movement so you can see the
              detectors react without walking it. Pings are tagged{" "}
              <code className="rounded bg-slate-100 px-1">demo</code>.
            </p>

            <label className="flex min-h-[44px] items-center gap-2.5">
              <input
                type="checkbox"
                checked={deviate}
                onChange={(e) => setDeviate(e.target.checked)}
                className="h-5 w-5 rounded border-slate-300 accent-violet-600"
              />
              <span className="text-[13px] text-slate-800">
                Wander off-route halfway (triggers a deviation alert)
              </span>
            </label>

            <Button variant="subtle" icon={PlayCircle} full onClick={runDemo}>
              Run demo walk
            </Button>
          </Card>
        </>
      )}
    </div>
  );
}

function Stat({ icon: Icon, label, value }) {
  return (
    <div className="px-3 py-3 text-center">
      <div className="mb-1 flex items-center justify-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        <Icon size={11} />
        {label}
      </div>
      <p className="text-[13px] font-bold text-slate-900">{value}</p>
    </div>
  );
}
