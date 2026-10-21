/**
 * 24-hour risk strip for a location.
 *
 * The area-risk model already takes time-of-day as a feature, so this is the
 * same model asked about later hours. It answers the question a tourist
 * actually has — "it's fine now, but what about when I head back tonight?"
 */
import { useEffect, useState } from "react";
import { Clock, TrendingDown, TrendingUp } from "lucide-react";
import { api } from "../lib/api";
import { riskLevel } from "../lib/format";
import { Card, Spinner } from "./ui";

function hourLabel(iso) {
  const d = new Date(iso);
  const h = d.getHours();
  if (h === 0) return "12a";
  if (h === 12) return "12p";
  return h < 12 ? `${h}a` : `${h - 12}p`;
}

export default function RiskForecast({ lat, lon, title = "Risk through the day" }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState(false);

  useEffect(() => {
    if (lat == null || lon == null) return;
    let cancelled = false;
    setLoading(true);
    setErr(false);
    api
      .forecast(lat, lon, 24)
      .then((d) => !cancelled && setData(d))
      .catch(() => !cancelled && setErr(true))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [lat, lon]);

  if (lat == null || lon == null) return null;

  if (loading) {
    return (
      <Card className="flex items-center justify-center p-6">
        <Spinner className="text-slate-400" />
      </Card>
    );
  }
  if (err || !data?.model_available) return null;

  // Scale bars against the worst hour so the shape is readable even when all
  // the scores are low.
  const peak = Math.max(...data.points.map((p) => p.risk_score ?? 0), 0.01);
  const nowHour = new Date().getHours();

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center gap-2">
        <Clock size={15} className="text-slate-500" />
        <h3 className="text-[13px] font-bold uppercase tracking-wide text-slate-600">
          {title}
        </h3>
      </div>

      <div className="flex items-end gap-[3px]" style={{ height: 68 }}>
        {data.points.map((p) => {
          const score = p.risk_score ?? 0;
          const { color } = riskLevel(p.risk_score);
          const isNow = new Date(p.when).getHours() === nowHour;
          return (
            <div
              key={p.when}
              className="group flex flex-1 flex-col items-center justify-end"
              style={{ height: "100%" }}
              title={`${hourLabel(p.when)} · ${p.label} (${score.toFixed(2)})`}
            >
              <div
                className="w-full rounded-sm transition-all"
                style={{
                  height: `${Math.max(6, (score / peak) * 100)}%`,
                  backgroundColor: color,
                  opacity: isNow ? 1 : 0.65,
                  outline: isNow ? "2px solid #0f172a" : "none",
                  outlineOffset: isNow ? "1px" : 0,
                }}
              />
            </div>
          );
        })}
      </div>

      {/* Sparse hour labels — one per 6h keeps it legible at phone width. */}
      <div className="mt-1.5 flex justify-between text-[10px] text-slate-400">
        {data.points
          .filter((_, i) => i % 6 === 0)
          .map((p) => (
            <span key={p.when}>{hourLabel(p.when)}</span>
          ))}
        <span>{hourLabel(data.points[data.points.length - 1].when)}</span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 border-t border-slate-100 pt-3">
        {data.safest && (
          <Highlight
            icon={TrendingDown}
            tone="text-emerald-600"
            label="Safest around"
            value={hourLabel(data.safest.when)}
            sub={data.safest.label}
          />
        )}
        {data.riskiest && (
          <Highlight
            icon={TrendingUp}
            tone="text-orange-600"
            label="Riskiest around"
            value={hourLabel(data.riskiest.when)}
            sub={data.riskiest.label}
          />
        )}
      </div>
    </Card>
  );
}

function Highlight({ icon: Icon, tone, label, value, sub }) {
  return (
    <div className="flex items-center gap-2">
      <Icon size={15} className={`shrink-0 ${tone}`} />
      <div className="min-w-0">
        <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
        <p className="text-[13px] font-bold text-slate-900">
          {value} <span className="font-medium capitalize text-slate-500">· {sub}</span>
        </p>
      </div>
    </div>
  );
}
