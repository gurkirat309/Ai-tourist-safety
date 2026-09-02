import { useEffect, useState } from "react";
import { UserRound, MapPin, Phone, Activity, ShieldAlert, Globe, CheckCircle, Navigation } from "lucide-react";
import { api } from "../lib/api";
import { TOURIST_STATUS_STYLES, riskLevel, fmtTime, titleCase } from "../lib/format";
import { Badge, Spinner, Empty, ProgressBar } from "./ui";

export default function TouristDetail({ touristId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!touristId) return;
    let alive = true;
    setLoading(true);
    api
      .policeTourist(touristId)
      .then((d) => alive && (setData(d), setErr(null)))
      .catch((e) => alive && setErr(e.message))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [touristId]);

  if (loading)
    return (
      <div className="flex h-48 flex-col items-center justify-center gap-2 text-slate-400">
        <Spinner size={24} />
        <span className="text-xs">Loading tourist record…</span>
      </div>
    );
  if (err) return <p className="text-sm text-rose-600">{err}</p>;
  if (!data) return <Empty>No tourist profile found.</Empty>;

  const lvl = riskLevel(data.area_risk_score);

  return (
    <div className="space-y-6">
      {/* Profile Dossier Header */}
      <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-blue-50 text-blue-600 font-bold font-mono text-sm shadow-2xs">
              {(data.display_name || "T").slice(0, 2).toUpperCase()}
            </div>
            <div>
              <h4 className="text-base font-bold text-slate-900 leading-tight">
                {data.display_name || "Unnamed Tourist"}
              </h4>
              <span className="text-[11px] text-slate-400 font-mono">ID: {data.id.slice(0, 8)}...</span>
            </div>
          </div>
          <Badge className={TOURIST_STATUS_STYLES[data.status]}>{data.status}</Badge>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 pt-2 border-t border-slate-200/60">
          <div className="flex items-center gap-1.5">
            <Globe size={13} className="text-slate-400" />
            <span>Nationality: <strong>{data.nationality || "International"}</strong></span>
          </div>
          <div className="flex items-center gap-1.5">
            <CheckCircle size={13} className="text-emerald-500" />
            <span>Consent: <strong>{data.consent_given ? "Authorized" : "Pending"}</strong></span>
          </div>
        </div>

        {data.emergency_contact && (
          <div className="flex items-center justify-between rounded-lg bg-white/80 p-2.5 border border-slate-200/60 text-xs">
            <span className="text-slate-500 flex items-center gap-1.5">
              <Phone size={13} className="text-slate-400" /> Emergency Phone:
            </span>
            <strong className="text-slate-800 font-mono">{data.emergency_contact}</strong>
          </div>
        )}

        {data.last_position && (
          <div className="rounded-lg bg-white/80 p-2.5 border border-slate-200/60 text-xs space-y-1">
            <div className="flex items-center justify-between">
              <span className="text-slate-500 flex items-center gap-1.5">
                <MapPin size={13} className="text-slate-400" /> Last Known Coordinates:
              </span>
              <span className="font-mono font-semibold text-slate-800">
                {data.last_position.lat.toFixed(4)}, {data.last_position.lon.toFixed(4)}
              </span>
            </div>
            {data.zone_name && (
              <div className="text-[11px] text-blue-700 font-medium">
                Within Zone: {data.zone_name}
              </div>
            )}
          </div>
        )}

        {data.area_risk_score != null && (
          <div className="rounded-lg bg-white/80 p-2.5 border border-slate-200/60 text-xs space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-slate-500">Local Area Risk:</span>
              <span className="font-bold" style={{ color: lvl.color }}>
                {data.area_risk_score.toFixed(3)} · {lvl.label}
              </span>
            </div>
            <ProgressBar value={Math.round((data.area_risk_score || 0) * 100)} max={100} color={lvl.color} height={5} />
          </div>
        )}
      </div>

      {/* Incident History */}
      <div>
        <SectionHeader icon={ShieldAlert} label="Associated Incident History" />
        {data.incidents.length === 0 ? (
          <Empty>No incidents triggered for this tourist.</Empty>
        ) : (
          <div className="space-y-1.5">
            {data.incidents.map((i) => (
              <div
                key={i.id}
                className="flex items-center justify-between rounded-lg border border-slate-200/80 bg-white px-3 py-2 text-xs shadow-2xs"
              >
                <span className="font-semibold text-slate-800">{titleCase(i.incident_type)}</span>
                <span className="text-[11px] text-slate-400 font-mono">{fmtTime(i.detected_at)}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* GPS Location Ping Stream */}
      <div>
        <SectionHeader icon={Activity} label={`Recent GPS Pings (${data.recent_pings.length} Recorded)`} />
        {data.recent_pings.length === 0 ? (
          <Empty>No recent GPS pings received.</Empty>
        ) : (
          <div className="max-h-48 space-y-1 overflow-y-auto pr-1">
            {data.recent_pings.map((p, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-md bg-slate-50/80 px-2.5 py-1.5 text-xs text-slate-600 font-mono border border-slate-100"
              >
                <span className="flex items-center gap-1.5">
                  <Navigation size={10} className="text-blue-500" />
                  {p.lat.toFixed(4)}, {p.lon.toFixed(4)}
                </span>
                <span className="text-[10px] text-slate-400">{fmtTime(p.recorded_at)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SectionHeader({ icon: Icon, label }) {
  return (
    <div className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-500">
      {Icon && <Icon size={14} className="text-slate-400" />}
      <span>{label}</span>
    </div>
  );
}
