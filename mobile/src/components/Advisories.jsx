/**
 * Nearby advisories, sourced from the Risk Intelligence agent.
 *
 * The backend sanitizes these: a tourist sees the *kind* of thing reported
 * nearby and what to do about it, never the incident's headline, description
 * or source article. Those stay police-only.
 */
import { useEffect, useState } from "react";
import {
  Megaphone,
  ShieldAlert,
  CloudRain,
  Car,
  HeartPulse,
  Info,
  Users,
} from "lucide-react";
import { api } from "../lib/api";
import { timeAgo } from "../lib/format";
import { Card, Chip, Spinner } from "./ui";

const TYPE_STYLE = {
  crime: { icon: ShieldAlert, chip: "bg-rose-100 text-rose-700", label: "Safety" },
  civil_unrest: { icon: Users, chip: "bg-orange-100 text-orange-700", label: "Unrest" },
  natural_hazard: { icon: CloudRain, chip: "bg-sky-100 text-sky-700", label: "Hazard" },
  accident: { icon: Car, chip: "bg-amber-100 text-amber-800", label: "Accident" },
  health: { icon: HeartPulse, chip: "bg-violet-100 text-violet-700", label: "Health" },
  advisory: { icon: Megaphone, chip: "bg-blue-100 text-blue-700", label: "Advisory" },
  other: { icon: Info, chip: "bg-slate-100 text-slate-700", label: "Notice" },
};

export default function Advisories({ refreshKey, radiusM = 5000, sinceHours = 48 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api
      .advisories({ radius_m: radiusM, since_hours: sinceHours })
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setData(null))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [refreshKey, radiusM, sinceHours]);

  if (loading) {
    return (
      <Card className="flex items-center justify-center p-6">
        <Spinner className="text-slate-400" />
      </Card>
    );
  }

  // Nothing nearby is the normal case — stay quiet rather than show an
  // empty box that reads like a failure.
  if (!data?.advisories?.length) return null;

  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between px-4 pt-4 pb-2">
        <div className="flex items-center gap-2">
          <Megaphone size={15} className="text-slate-500" />
          <h3 className="text-[13px] font-bold uppercase tracking-wide text-slate-600">
            Near you
          </h3>
        </div>
        <span className="text-[11px] text-slate-400">
          last {data.since_hours}h · {Math.round(data.radius_m / 1000)} km
        </span>
      </div>

      <ul className="divide-y divide-slate-100">
        {data.advisories.map((a, i) => {
          const style = TYPE_STYLE[a.event_type] || TYPE_STYLE.other;
          const Icon = style.icon;
          return (
            <li key={i} className="flex items-start gap-3 px-4 py-3">
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-100">
                <Icon size={15} className="text-slate-600" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="mb-1 flex flex-wrap items-center gap-1.5">
                  <Chip className={style.chip}>{style.label}</Chip>
                  {a.area && (
                    <span className="text-[11px] font-medium text-slate-500">
                      {a.area}
                    </span>
                  )}
                  <span className="text-[11px] text-slate-400">
                    · {timeAgo(a.event_time)}
                  </span>
                </div>
                <p className="text-[13px] leading-snug text-slate-800">{a.advice}</p>
              </div>
            </li>
          );
        })}
      </ul>

      <p className="border-t border-slate-100 bg-slate-50 px-4 py-2 text-[10px] leading-relaxed text-slate-500">
        Area-level awareness only. Detailed reports go to the control room, not
        to travellers.
      </p>
    </Card>
  );
}
