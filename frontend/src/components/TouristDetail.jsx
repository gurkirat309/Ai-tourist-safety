import { useEffect, useState } from "react";
import { UserRound, MapPin, Phone, Activity, ShieldAlert } from "lucide-react";
import { api } from "../lib/api";
import { TOURIST_STATUS_STYLES, riskLevel, fmtTime, titleCase } from "../lib/format";
import { Badge, Spinner, Empty } from "./ui";

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
    return <div className="flex h-40 items-center justify-center"><Spinner /></div>;
  if (err) return <p className="text-sm text-red-600">{err}</p>;
  if (!data) return <Empty>No tourist.</Empty>;

  const lvl = riskLevel(data.area_risk_score);
  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center gap-2">
          <UserRound size={18} className="text-brand-600" />
          <h4 className="text-base font-semibold text-slate-800">
            {data.display_name || "Unnamed tourist"}
          </h4>
          <Badge className={TOURIST_STATUS_STYLES[data.status]}>{data.status}</Badge>
        </div>
        <div className="mt-2 space-y-1 text-sm text-slate-500">
          <div>Nationality: {data.nationality || "—"}</div>
          {data.emergency_contact && (
            <div className="flex items-center gap-2">
              <Phone size={14} /> {data.emergency_contact}
            </div>
          )}
          <div>Consent: {data.consent_given ? "given" : "none"}</div>
          {data.last_position && (
            <div className="flex items-center gap-2">
              <MapPin size={14} /> {data.last_position.lat.toFixed(4)}, {data.last_position.lon.toFixed(4)}
              {data.zone_name ? ` · ${data.zone_name}` : ""}
            </div>
          )}
          {data.area_risk_score != null && (
            <div>
              Area risk:{" "}
              <span className="font-medium" style={{ color: lvl.color }}>
                {data.area_risk_score.toFixed(3)} · {lvl.label}
              </span>
            </div>
          )}
        </div>
      </div>

      <Section icon={ShieldAlert} label="Incidents">
        {data.incidents.length === 0 ? (
          <Empty>No incidents.</Empty>
        ) : (
          <div className="space-y-2">
            {data.incidents.map((i) => (
              <div key={i.id} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2 text-sm">
                <span className="font-medium text-slate-700">{titleCase(i.incident_type)}</span>
                <span className="text-xs text-slate-400">{fmtTime(i.detected_at)}</span>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section icon={Activity} label={`Recent activity (${data.recent_pings.length} pings)`}>
        {data.recent_pings.length === 0 ? (
          <Empty>No location history.</Empty>
        ) : (
          <div className="max-h-48 space-y-1 overflow-auto">
            {data.recent_pings.map((p, i) => (
              <div key={i} className="flex items-center justify-between text-xs text-slate-500">
                <span>{p.lat.toFixed(4)}, {p.lon.toFixed(4)}</span>
                <span>{fmtTime(p.recorded_at)}</span>
              </div>
            ))}
          </div>
        )}
      </Section>
    </div>
  );
}

function Section({ icon: Icon, label, children }) {
  return (
    <div>
      <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
        {Icon && <Icon size={14} />} {label}
      </div>
      {children}
    </div>
  );
}
