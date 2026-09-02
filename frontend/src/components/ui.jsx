// Reusable UI primitives — clean, purposeful civic-safety design.

export function Card({
  title,
  subtitle,
  icon: Icon,
  action,
  children,
  className = "",
  bodyClassName = "p-5",
}) {
  return (
    <div
      className={`rounded-xl border border-slate-200/80 bg-white shadow-xs transition-shadow duration-200 hover:shadow-sm ${className}`}
    >
      {(title || action || Icon) && (
        <div className="flex items-center justify-between border-b border-slate-100/90 px-5 py-3.5">
          <div className="flex items-center gap-2.5">
            {Icon && (
              <div className="grid h-7 w-7 place-items-center rounded-lg bg-slate-100 text-slate-700">
                <Icon size={16} />
              </div>
            )}
            <div>
              <h3 className="text-sm font-semibold tracking-tight text-slate-900">{title}</h3>
              {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
            </div>
          </div>
          {action}
        </div>
      )}
      <div className={bodyClassName}>{children}</div>
    </div>
  );
}

export function StatCard({
  icon: Icon,
  label,
  value,
  tone = "brand",
  subtitle,
  pulse = false,
  badge,
}) {
  const tones = {
    brand: "bg-blue-50 text-blue-600 border-blue-100",
    emerald: "bg-emerald-50 text-emerald-600 border-emerald-100",
    amber: "bg-amber-50 text-amber-600 border-amber-100",
    red: "bg-rose-50 text-rose-600 border-rose-100",
    slate: "bg-slate-100 text-slate-600 border-slate-200",
  };

  return (
    <div className="relative overflow-hidden rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs transition-all duration-200 hover:-translate-y-0.5 hover:shadow-sm">
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {label}
          </div>
          <div className="text-2xl font-bold tracking-tight text-slate-900">{value}</div>
          {subtitle && <div className="text-xs text-slate-400">{subtitle}</div>}
        </div>
        <div className="flex items-center gap-2">
          {badge && (
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
              {badge}
            </span>
          )}
          <div className={`relative grid h-11 w-11 place-items-center rounded-xl border ${tones[tone]}`}>
            {pulse && (
              <span className="absolute -top-1 -right-1 flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
              </span>
            )}
            {Icon && <Icon size={20} />}
          </div>
        </div>
      </div>
    </div>
  );
}

export function Badge({ children, className = "", dot = false, dotColor = "bg-emerald-500" }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold tracking-wide ring-1 ring-inset ${className}`}
    >
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />}
      {children}
    </span>
  );
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  className = "",
  ...props
}) {
  const variants = {
    primary:
      "bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800 disabled:bg-blue-300 shadow-xs",
    danger:
      "bg-rose-600 text-white hover:bg-rose-700 active:bg-rose-800 disabled:bg-rose-300 shadow-xs",
    emerald:
      "bg-emerald-600 text-white hover:bg-emerald-700 active:bg-emerald-800 disabled:bg-emerald-300 shadow-xs",
    ghost:
      "bg-white text-slate-700 border border-slate-200 hover:bg-slate-50 hover:text-slate-900 active:bg-slate-100 shadow-xs",
    subtle:
      "bg-slate-100 text-slate-700 hover:bg-slate-200 active:bg-slate-300",
  };

  const sizes = {
    sm: "px-2.5 py-1.5 text-xs",
    md: "px-4 py-2 text-sm",
    lg: "px-5 py-2.5 text-base font-semibold",
  };

  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-150 active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-70 ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-600">
        {label}
      </span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-400">{hint}</span>}
    </label>
  );
}

export function Input(props) {
  return (
    <input
      className="w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition-all focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
      {...props}
    />
  );
}

export function Spinner({ size = 16, className = "" }) {
  return (
    <div
      style={{ width: size, height: size }}
      className={`animate-spin rounded-full border-2 border-slate-300 border-t-blue-600 ${className}`}
    />
  );
}

export function Empty({ children, icon: Icon }) {
  return (
    <div className="flex flex-col items-center justify-center py-8 text-center text-slate-400">
      {Icon && <Icon size={28} className="mb-2 opacity-50" />}
      <span className="text-sm font-medium">{children}</span>
    </div>
  );
}

export function ProgressBar({ value, max = 100, color = "#10b981", height = 6 }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div
      style={{ height }}
      className="w-full overflow-hidden rounded-full bg-slate-100"
    >
      <div
        style={{ width: `${pct}%`, backgroundColor: color }}
        className="h-full rounded-full transition-all duration-500 ease-out"
      />
    </div>
  );
}
