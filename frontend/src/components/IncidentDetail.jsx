import { useEffect, useState } from "react";
import {
  MapPin,
  Clock,
  ShieldAlert,
  ListChecks,
  PhoneCall,
  Bot,
  User,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import { api } from "../lib/api";
import { SEVERITY_STYLES, fmtTime, titleCase } from "../lib/format";
import { Badge, Spinner, Empty, Button } from "./ui";

export default function IncidentDetail({ incidentId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(null);
  const [acknowledged, setAcknowledged] = useState(false);

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
      setAcknowledged(false);
    };
  }, [incidentId]);

  if (loading) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-2 text-slate-400">
        <Spinner size={24} />
        <span className="text-xs">Loading incident dossier…</span>
      </div>
    );
  }

  if (err) return <p className="text-sm text-rose-600">{err}</p>;
  if (!data) return <Empty>No incident found.</Empty>;

  const signals = data.details?.signals || [];
  const areaRisk = data.details?.area_risk_score;
  const isVoiceCall = data.details?.trigger === "ai_voice_call";

  return (
    <div className="space-y-6">
      {/* Incident Dossier Header */}
      <div className="rounded-xl border border-slate-200/80 bg-slate-50/60 p-4 space-y-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="grid h-8 w-8 place-items-center rounded-lg bg-rose-50 text-rose-600">
              <ShieldAlert size={18} />
            </div>
            <div>
              <h4 className="text-base font-bold text-slate-900 leading-tight">
                {isVoiceCall ? "AI Emergency Voice Call" : titleCase(data.incident_type)}
              </h4>
              <span className="text-[11px] text-slate-400 font-mono">ID: {data.id.slice(0, 8)}...</span>
            </div>
          </div>
          <Badge
            className={
              data.status === "open"
                ? "bg-rose-100 text-rose-800 ring-rose-300"
                : "bg-slate-100 text-slate-700 ring-slate-200"
            }
          >
            {data.status}
          </Badge>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs text-slate-600 pt-2 border-t border-slate-200/60">
          <div className="flex items-center gap-1.5 font-mono">
            <Clock size={13} className="text-slate-400" />
            <span>{fmtTime(data.detected_at)}</span>
          </div>
          {data.location && (
            <div className="flex items-center gap-1.5 font-mono">
              <MapPin size={13} className="text-slate-400" />
              <span>{data.location.lat.toFixed(4)}, {data.location.lon.toFixed(4)}</span>
            </div>
          )}
        </div>

        {areaRisk != null && (
          <div className="text-xs text-slate-600 bg-white/80 rounded-md p-2 border border-slate-200/60 flex items-center justify-between">
            <span>Spatiotemporal Area Risk:</span>
            <span className="font-bold text-slate-800 font-mono">{areaRisk.toFixed(3)}</span>
          </div>
        )}
      </div>

      {/* Live AI Voice Call Transcript (If Applicable) */}
      {isVoiceCall && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <PhoneCall size={16} className="text-emerald-700" />
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-900">
                Two-Way Voice Session
              </span>
            </div>
            <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800 ring-1 ring-emerald-300">
              {data.details?.call_final_status || "Completed / Dispatched"}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs bg-white/80 rounded-lg p-2.5 border border-emerald-200/60">
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-bold">Dialed Tourist</span>
              <strong className="text-slate-800 font-mono">{data.details?.phone_called || "N/A"}</strong>
            </div>
            <div>
              <span className="text-slate-400 block text-[10px] uppercase font-bold">Call Duration</span>
              <strong className="text-slate-800 font-mono">
                {data.details?.call_duration_seconds ? `${data.details.call_duration_seconds}s` : "Recorded"}
              </strong>
            </div>
          </div>

          {/* Transcript Dialogue */}
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-emerald-900 mb-2">
              Live Call Audio Transcript
            </div>
            {(!data.details?.transcript || data.details.transcript.length === 0) ? (
              <p className="text-xs italic text-slate-500 bg-white/60 p-3 rounded-lg border border-dashed border-emerald-200">
                Call initiated. Waiting for speech input to be processed...
              </p>
            ) : (
              <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
                {data.details.transcript.map((t, i) => {
                  const isTourist = t.speaker === "tourist";
                  return (
                    <div
                      key={i}
                      className={`flex gap-2.5 ${isTourist ? "justify-start" : "justify-end"}`}
                    >
                      {isTourist && (
                        <div className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-slate-200 text-slate-700 text-xs">
                          <User size={12} />
                        </div>
                      )}
                      <div
                        className={`rounded-xl p-2.5 text-xs max-w-[85%] ${
                          isTourist
                            ? "bg-white border border-slate-200 text-slate-800 shadow-2xs"
                            : "bg-emerald-600 text-white shadow-2xs"
                        }`}
                      >
                        <div
                          className={`text-[10px] font-bold uppercase tracking-wider mb-0.5 ${
                            isTourist ? "text-slate-400" : "text-emerald-200"
                          }`}
                        >
                          {isTourist ? "Tourist (Spoken)" : "Suraksha AI Safety Assistant"}
                        </div>
                        <p className="leading-relaxed">{t.text || "(Silence or unclear input)"}</p>
                      </div>
                      {!isTourist && (
                        <div className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-emerald-700 text-white text-xs">
                          <Bot size={12} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Detection Signals */}
      <div>
        <SectionLabel icon={ListChecks}>Autonomous Detection Signals</SectionLabel>
        {signals.length === 0 ? (
          <Empty>No detection signals recorded for this incident.</Empty>
        ) : (
          <div className="space-y-2">
            {signals.map((s, i) => (
              <div
                key={i}
                className="flex items-start gap-2.5 rounded-lg border border-slate-200/80 bg-white p-2.5 text-xs shadow-2xs"
              >
                <Badge className={SEVERITY_STYLES[s.severity] || SEVERITY_STYLES.info}>
                  {s.severity}
                </Badge>
                <span className="text-slate-700 leading-snug">{s.reason}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Advisory Alerts */}
      <div>
        <SectionLabel icon={ShieldAlert}>AI Triage Recommended Actions</SectionLabel>
        {data.alerts.length === 0 ? (
          <Empty>No triage alerts associated.</Empty>
        ) : (
          <div className="space-y-3">
            {data.alerts.map((a) => (
              <div
                key={a.id}
                className="rounded-xl border border-slate-200 bg-white p-3.5 shadow-2xs space-y-2"
              >
                <div className="flex items-center justify-between">
                  <Badge className={SEVERITY_STYLES[a.severity]}>{a.severity}</Badge>
                  <span className="text-[11px] text-slate-400 font-mono">{a.created_by}</span>
                </div>
                {a.summary && (
                  <p className="text-xs font-semibold text-slate-800">{a.summary}</p>
                )}
                {a.recommended_action && (
                  <ul className="space-y-1.5 pt-1 border-t border-slate-100">
                    {a.recommended_action
                      .split("\n")
                      .filter(Boolean)
                      .map((line, i) => (
                        <li key={i} className="flex gap-2 text-xs text-slate-600">
                          <span className="text-blue-600 font-bold">›</span>
                          <span>{line}</span>
                        </li>
                      ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Police Operator Action Bar */}
      <div className="pt-2 border-t border-slate-200 space-y-2">
        {!acknowledged ? (
          <Button
            onClick={() => setAcknowledged(true)}
            className="w-full bg-slate-900 hover:bg-black text-white py-2.5"
          >
            <CheckCircle2 size={16} /> Acknowledge & Log to PCR 112
          </Button>
        ) : (
          <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-2.5 text-xs text-emerald-800 font-medium flex items-center justify-center gap-1.5">
            <CheckCircle2 size={15} className="text-emerald-600" />
            <span>Incident Acknowledged by Operator</span>
          </div>
        )}
      </div>
    </div>
  );
}

function SectionLabel({ icon: Icon, children }) {
  return (
    <div className="mb-2 flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-500">
      {Icon && <Icon size={14} className="text-slate-400" />}
      <span>{children}</span>
    </div>
  );
}
