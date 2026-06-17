import { useEffect, useState } from "react";
import { MapPin, Clock, ShieldAlert, ListChecks } from "lucide-react";
import { api } from "../lib/api";
import { SEVERITY_STYLES, fmtTime, titleCase } from "../lib/format";
import { Badge, Spinner, Empty } from "./ui";

export default function IncidentDetail({ incidentId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);

  useEffect(() => {
    if (!incidentId) return;
    let alive = true;
    setLoading(true);
    api
      .incident(incidentId)
      .then((d) => alive && (setData(d), setErr(null)))
      .catch((e) => alive && setErr(e.message))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [incidentId]);

  if (loading)
    return (
      <div className="flex h-40 items-center justify-center">
        <Spinner />
      </div>
    );
  if (err) return <p className="text-sm text-red-600">{err}</p>;
  if (!data) return <Empty>No incident.</Empty>;

  const signals = data.details?.signals || [];
  const areaRisk = data.details?.area_risk_score;

  return (
    <div className="space-y-5">
      <div>
        <div className="flex items-center gap-2">
          <ShieldAlert size={18} className="text-brand-600" />
          <h4 className="text-base font-semibold text-slate-800">
            {titleCase(data.incident_type)}
          </h4>
          <Badge className="bg-slate-100 text-slate-600 ring-slate-200">{data.status}</Badge>
        </div>
        <div className="mt-2 space-y-1 text-sm text-slate-500">
          <div className="flex items-center gap-2">
            <Clock size={14} /> {fmtTime(data.detected_at)}
          </div>
          {data.location && (
            <div className="flex items-center gap-2">
              <MapPin size={14} /> {data.location.lat.toFixed(4)}, {data.location.lon.toFixed(4)}
            </div>
          )}
          {areaRisk != null && (
            <div>
              Area-risk score:{" "}
              <span className="font-medium text-slate-700">{areaRisk.toFixed(3)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Detection signals */}
      <div>
        <SectionLabel icon={ListChecks}>Detection signals</SectionLabel>
        {signals.length === 0 ? (
          <Empty>No signals recorded.</Empty>
        ) : (
          <div className="space-y-2">
            {signals.map((s, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <Badge className={SEVERITY_STYLES[s.severity] || SEVERITY_STYLES.info}>
                  {s.severity}
                </Badge>
                <span className="text-slate-600">{s.reason}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Advisory alerts */}
      <div>
        <SectionLabel icon={ShieldAlert}>Advisory alerts</SectionLabel>
        {data.alerts.length === 0 ? (
          <Empty>No alerts.</Empty>
        ) : (
          <div className="space-y-3">
            {data.alerts.map((a) => (
              <div key={a.id} className="rounded-lg border border-slate-200 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <Badge className={SEVERITY_STYLES[a.severity]}>{a.severity}</Badge>
                  <span className="text-xs text-slate-400">{a.created_by}</span>
                </div>
                {a.summary && <p className="text-sm text-slate-700">{a.summary}</p>}
                {a.recommended_action && (
                  <ul className="mt-2 space-y-1">
                    {a.recommended_action.split("\n").filter(Boolean).map((line, i) => (
                      <li key={i} className="flex gap-2 text-sm text-slate-600">
                        <span className="text-brand-500">›</span>
                        {line}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function SectionLabel({ icon: Icon, children }) {
  return (
    <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
      {Icon && <Icon size={14} />}
      {children}
    </div>
  );
}
