/**
 * The headline safety card.
 *
 * Shows the backend's verdict, never a locally computed one — the browser
 * must not second-guess the deterministic detection layer.
 */
import {
  ShieldCheck,
  TriangleAlert,
  Siren,
  Navigation,
  MapPin,
  Clock,
  Route as RouteIcon,
  Users,
  Fence,
  TimerOff,
  Activity,
} from "lucide-react";
import { Card, Chip, Meter } from "./ui";
import { STATUS_CONFIG, riskLevel, timeAgo, fmtDistance, titleCase } from "../lib/format";

const ICONS = {
  safe: ShieldCheck,
  warning: TriangleAlert,
  critical: Siren,
  no_data: Navigation,
};

// Per-signal icon, so "too crowded here" doesn't look identical to "you've
// wandered off your route" at a glance.
const WARNING_ICONS = {
  crowd_density: Users,
  geofence_breach: Fence,
  inactivity: TimerOff,
  route_deviation: RouteIcon,
};

// The LSTM anomaly reports as route_deviation; its source distinguishes it.
function warningIcon(w) {
  if (w.source === "ml.trajectory_lstm") return Activity;
  return WARNING_ICONS[w.type] || TriangleAlert;
}

export default function StatusCard({ status, tracking, mode, lastSentAt }) {
  const key = status?.status || "no_data";
  const cfg = STATUS_CONFIG[key];
  const Icon = ICONS[key];
  const risk = riskLevel(status?.area_risk_score);

  return (
    <Card className={`overflow-hidden ${cfg.bg} ring-1 ${cfg.ring}`}>
      <div className="px-5 pt-5 pb-4">
        <div className="flex items-start gap-3.5">
          <div
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full
              bg-white/80 ${key === "safe" && tracking ? "animate-radar" : ""}
              ${key === "critical" ? "animate-danger" : ""}`}
          >
            <Icon size={24} className={cfg.text} />
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h2 className={`text-lg font-bold leading-tight ${cfg.text}`}>
                {cfg.title}
              </h2>
              {mode === "demo" && (
                <Chip className="bg-violet-100 text-violet-700">DEMO</Chip>
              )}
            </div>

            <p className={`mt-0.5 text-[13px] ${cfg.text} opacity-80`}>
              {tracking ? (
                <>
                  Sharing location
                  {lastSentAt ? ` · sent ${timeAgo(lastSentAt.toISOString())}` : ""}
                </>
              ) : status?.last_seen ? (
                <>Paused · last seen {timeAgo(status.last_seen)}</>
              ) : (
                "Start sharing so help can find you"
              )}
            </p>
          </div>
        </div>

        {/* Area risk */}
        {status?.area_risk_score != null && (
          <div className="mt-4">
            <div className="mb-1.5 flex items-center justify-between text-[12px] font-medium">
              <span className={`${cfg.text} opacity-75`}>Area risk right now</span>
              <span style={{ color: risk.color }} className="font-bold uppercase">
                {risk.label}
              </span>
            </div>
            <Meter value={status.area_risk_score} color={risk.color} />
          </div>
        )}
      </div>

      {/* Facts strip */}
      <div className="grid grid-cols-3 divide-x divide-white/70 border-t border-white/70 bg-white/50">
        <Fact
          icon={MapPin}
          label="Zone"
          value={status?.zone?.name ? titleCase(status.zone.risk_category) : "—"}
          sub={status?.zone?.name || "Outside mapped zones"}
        />
        <Fact
          icon={RouteIcon}
          label="Route"
          value={
            !status?.has_route
              ? "None"
              : status?.on_route === true
                ? "On track"
                : status?.on_route === false
                  ? "Off route"
                  : "—"
          }
          sub={
            status?.deviation_m != null
              ? `${fmtDistance(status.deviation_m)} away`
              : "No trip planned"
          }
        />
        <Fact
          icon={Clock}
          label="Last seen"
          value={status?.last_seen ? timeAgo(status.last_seen) : "—"}
          sub={status?.last_position ? "Position known" : "No position yet"}
        />
      </div>

      {/* Safety warnings — advisory text only, never crime specifics. */}
      {status?.warnings?.length > 0 && (
        <ul className="divide-y divide-slate-100 border-t border-white/70 bg-white">
          {status.warnings.map((w, i) => {
            const WIcon = warningIcon(w);
            return (
            <li key={i} className="flex items-start gap-2.5 px-5 py-3">
              <WIcon
                size={15}
                className={`mt-0.5 shrink-0 ${
                  w.severity === "critical" ? "text-rose-500" : "text-amber-500"
                }`}
              />
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-slate-800">{w.reason}</p>
                <p className="text-[11px] text-slate-500">
                  {titleCase(w.type)} · {Math.round((w.confidence ?? 0) * 100)}% confidence
                </p>
              </div>
            </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

function Fact({ icon: Icon, label, value, sub }) {
  return (
    <div className="px-3 py-3 text-center">
      <div className="mb-1 flex items-center justify-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        <Icon size={11} />
        {label}
      </div>
      <p className="truncate text-[13px] font-bold text-slate-900">{value}</p>
      <p className="truncate text-[10px] text-slate-500">{sub}</p>
    </div>
  );
}
