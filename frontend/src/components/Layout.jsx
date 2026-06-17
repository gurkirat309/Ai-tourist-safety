import { NavLink, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";
import { LayoutDashboard, UserRound, ShieldCheck, Activity } from "lucide-react";
import { api } from "../lib/api";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/portal", label: "Tourist Portal", icon: UserRound },
];

function HealthDot() {
  const [ok, setOk] = useState(null);
  useEffect(() => {
    let alive = true;
    const check = () =>
      api
        .health()
        .then((d) => alive && setOk(d.status === "ok"))
        .catch(() => alive && setOk(false));
    check();
    const t = setInterval(check, 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);
  const color = ok == null ? "bg-slate-400" : ok ? "bg-emerald-400" : "bg-red-400";
  return (
    <div className="flex items-center gap-2 text-xs text-slate-400">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      {ok == null ? "checking…" : ok ? "API healthy" : "API offline"}
    </div>
  );
}

export default function Layout() {
  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="flex w-64 shrink-0 flex-col bg-slate-900 text-slate-300">
        <div className="flex items-center gap-2 px-6 py-5 text-white">
          <ShieldCheck className="text-brand-500" size={24} />
          <div className="leading-tight">
            <div className="font-semibold">Tourist Safety</div>
            <div className="text-xs text-slate-400">Control Center</div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-2">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-brand-600 text-white"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-800 px-6 py-4">
          <HealthDot />
          <div className="mt-1 text-[11px] text-slate-500">Bengaluru · synthetic data</div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-slate-200 bg-white px-6 py-3">
          <Activity size={18} className="text-brand-600" />
          <span className="text-sm font-medium text-slate-600">
            AI-Orchestrated Tourist Safety & Incident Intelligence
          </span>
        </header>
        <main className="min-w-0 flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
