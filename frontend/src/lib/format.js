// Shared presentation helpers: severity / risk-category colors (no purple).

// Tailwind class sets for alert severities.
export const SEVERITY_STYLES = {
  info: "bg-slate-100 text-slate-700 ring-slate-200",
  low: "bg-emerald-100 text-emerald-700 ring-emerald-200",
  medium: "bg-amber-100 text-amber-800 ring-amber-200",
  high: "bg-orange-100 text-orange-700 ring-orange-200",
  critical: "bg-red-100 text-red-700 ring-red-200",
};

// Zone risk categories.
export const RISK_STYLES = {
  low: "bg-emerald-100 text-emerald-700 ring-emerald-200",
  moderate: "bg-amber-100 text-amber-800 ring-amber-200",
  high: "bg-orange-100 text-orange-700 ring-orange-200",
  restricted: "bg-red-100 text-red-700 ring-red-200",
};

// Map a 0..1 risk score to a label + hex color (for the map / meters).
export function riskLevel(score) {
  if (score == null) return { label: "n/a", color: "#94a3b8" };
  if (score >= 0.5) return { label: "high", color: "#ea580c" };
  if (score >= 0.3) return { label: "elevated", color: "#d97706" };
  if (score >= 0.15) return { label: "moderate", color: "#ca8a04" };
  return { label: "low", color: "#059669" };
}

// Hex colors for zone polygons on the map.
export const ZONE_COLORS = {
  low: "#10b981",
  moderate: "#f59e0b",
  high: "#f97316",
  restricted: "#ef4444",
};

// Tourist live-status → badge classes + map marker hex.
export const TOURIST_STATUS_STYLES = {
  safe: "bg-emerald-100 text-emerald-700 ring-emerald-200",
  inactive: "bg-slate-100 text-slate-600 ring-slate-200",
  alert: "bg-orange-100 text-orange-700 ring-orange-200",
  panic: "bg-red-100 text-red-700 ring-red-200",
  no_data: "bg-slate-100 text-slate-500 ring-slate-200",
};
export const TOURIST_STATUS_COLORS = {
  safe: "#10b981",
  inactive: "#94a3b8",
  alert: "#f97316",
  panic: "#ef4444",
  no_data: "#cbd5e1",
};

export function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function titleCase(s) {
  return (s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
