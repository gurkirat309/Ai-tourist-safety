/**
 * Route chooser: safest vs fastest, with the trade-off stated plainly.
 *
 * Routing engines optimise for time. The whole point of this product is that
 * the quickest way is not always the one you should take — so the comparison
 * has to be visible, and the cost of choosing safety has to be honest.
 */
import { ShieldCheck, Zap, Check } from "lucide-react";
import { riskLevel, fmtDistance, fmtDuration } from "../lib/format";
import { Card, Meter, Chip } from "./ui";

export default function RouteOptions({ trip, onSelect, busy }) {
  const options = trip?.alternatives || [];
  // With a single candidate there is no choice to present.
  if (options.length < 2) return null;

  const selected = options.find((o) => o.is_selected);

  return (
    <Card className="overflow-hidden">
      <div className="px-4 pt-4 pb-1">
        <h3 className="text-[13px] font-bold uppercase tracking-wide text-slate-600">
          Choose your route
        </h3>
        {trip.trade_off && selected?.is_safest && (
          <p className="mt-1 text-[12px] text-emerald-700">
            Safest route: {trip.trade_off}.
          </p>
        )}
      </div>

      <ul className="divide-y divide-slate-100">
        {options.map((o) => {
          const risk = riskLevel(o.safety?.max_score);
          const active = o.is_selected;
          // Switching preference re-plans; with 2 options the labels map 1:1.
          const prefer = o.is_safest ? "safest" : "fastest";

          return (
            <li key={o.index}>
              <button
                type="button"
                disabled={busy || active}
                onClick={() => onSelect(prefer)}
                className={`flex w-full items-start gap-3 px-4 py-3 text-left transition-colors
                  ${active ? "bg-blue-50" : "active:bg-slate-50"}`}
              >
                <div
                  className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full
                    ${active ? "bg-blue-600 text-white" : "bg-slate-100 text-slate-600"}`}
                >
                  {active ? (
                    <Check size={15} />
                  ) : o.is_safest ? (
                    <ShieldCheck size={15} />
                  ) : (
                    <Zap size={15} />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex flex-wrap items-center gap-1.5">
                    <span className="text-[14px] font-semibold text-slate-900">
                      {o.is_safest ? "Safest" : "Fastest"}
                    </span>
                    {o.is_safest && o.is_fastest && (
                      <Chip className="bg-emerald-100 text-emerald-700">
                        Best of both
                      </Chip>
                    )}
                  </div>

                  <p className="text-[12px] text-slate-600">
                    {fmtDuration(o.duration_s)} · {fmtDistance(o.distance_m)}
                  </p>

                  {o.safety?.max_score != null && (
                    <div className="mt-2">
                      <div className="mb-1 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wide">
                        <span className="text-slate-500">Peak risk</span>
                        <span style={{ color: risk.color }}>{risk.label}</span>
                      </div>
                      <Meter value={o.safety.max_score} color={risk.color} />
                    </div>
                  )}
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
