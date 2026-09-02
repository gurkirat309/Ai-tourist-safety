import { NavLink, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  UserRound,
  ShieldCheck,
  Activity,
  LogOut,
  Radio,
  Clock,
  ExternalLink,
} from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

// Nav items per role — each role only sees its own area.
const NAV_BY_ROLE = {
  police: [
    { to: "/", label: "Command Dashboard", icon: LayoutDashboard, end: true },
  ],
  tourist: [
    { to: "/portal", label: "My Travel Safety", icon: UserRound },
  ],
};

function LiveClock() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="hidden sm:flex items-center gap-2 text-xs text-slate-500 font-mono bg-slate-100/80 px-3 py-1.5 rounded-lg border border-slate-200/60">
      <Clock size={13} className="text-slate-400" />
      <span>
        {time.toLocaleTimeString("en-IN", {
          timeZone: "Asia/Kolkata",
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
          hour12: true,
        })} IST
      </span>
    </div>
  );
}

function SystemStatusIndicator() {
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

  return (
    <div className="flex items-center justify-between rounded-lg bg-slate-800/60 p-2.5 border border-slate-700/50">
      <div className="flex items-center gap-2">
        <span className="relative flex h-2 w-2">
          {ok && (
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          )}
          <span
            className={`relative inline-flex rounded-full h-2 w-2 ${
              ok == null
                ? "bg-amber-400"
                : ok
                ? "bg-emerald-400"
                : "bg-rose-500"
            }`}
          />
        </span>
        <span className="text-xs font-medium text-slate-300">
          {ok == null ? "Checking Core..." : ok ? "Active Shield" : "Engine Offline"}
        </span>
      </div>
      <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400">
        AI v1.0
      </span>
    </div>
  );
}

export default function Layout() {
  const { user, logout } = useAuth();
  const nav = NAV_BY_ROLE[user?.role] || [];

  // Generate initials for the user avatar
  const initials = (user?.email || "TS")
    .split("@")[0]
    .slice(0, 2)
    .toUpperCase();

  return (
    <div className="flex h-full bg-slate-50 text-slate-900">
      {/* Tactical Midnight Sidebar */}
      <aside className="flex w-64 shrink-0 flex-col bg-[#0B1120] text-slate-300 border-r border-slate-800/80 shadow-lg">
        {/* Brand Header */}
        <div className="flex items-center gap-3 px-6 py-5 border-b border-slate-800/60">
          <div className="relative grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 text-white shadow-md shadow-blue-500/20">
            <ShieldCheck size={22} className="stroke-[2.2]" />
          </div>
          <div className="leading-tight">
            <div className="font-bold text-white text-base tracking-tight flex items-center gap-1.5">
              <span>Suraksha</span>
              <span className="text-[10px] uppercase bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded font-mono font-bold tracking-wider">
                AI
              </span>
            </div>
            <div className="text-xs text-slate-400 font-medium">
              {user?.role === "police" ? "Police Control Room" : "Tourist Safety Guard"}
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1.5 px-3 py-4">
          <div className="px-3 mb-2 text-[11px] font-bold uppercase tracking-wider text-slate-500">
            Navigation
          </div>
          {nav.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `group flex items-center justify-between rounded-xl px-3.5 py-2.5 text-sm font-semibold transition-all duration-150 ${
                  isActive
                    ? "bg-blue-600 text-white shadow-sm shadow-blue-600/30"
                    : "text-slate-400 hover:bg-slate-800/70 hover:text-slate-200"
                }`
              }
            >
              <div className="flex items-center gap-3">
                <Icon
                  size={18}
                  className="transition-transform group-hover:scale-110 duration-150"
                />
                <span>{label}</span>
              </div>
              <Radio size={12} className="opacity-40" />
            </NavLink>
          ))}
        </nav>

        {/* System Health & User Profile */}
        <div className="space-y-3.5 border-t border-slate-800/80 p-4">
          <SystemStatusIndicator />

          {/* User Account Card */}
          <div className="flex items-center justify-between rounded-xl bg-slate-800/40 p-2.5 border border-slate-700/40">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="grid h-8 w-8 place-items-center rounded-lg bg-blue-600/20 text-blue-400 text-xs font-bold font-mono">
                {initials}
              </div>
              <div className="min-w-0">
                <div className="truncate text-xs font-semibold text-white">
                  {user?.email}
                </div>
                <div className="text-[10px] uppercase font-bold tracking-wider text-blue-400">
                  {user?.role === "police" ? "Authority · Officer" : "Registered Tourist"}
                </div>
              </div>
            </div>
            <button
              onClick={logout}
              title="Sign Out"
              className="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-700/60 hover:text-white"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-slate-50/70">
        {/* Top Header */}
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200/80 bg-white/95 px-6 backdrop-blur-sm shadow-xs">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Bengaluru Metropolitan Region</span>
            </div>
            <span className="text-slate-300">|</span>
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <Activity size={14} className="text-blue-600" />
              <span className="font-medium">Live Spatiotemporal Intelligence</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <LiveClock />
            <div className="hidden md:inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Geofence Guard Active
            </div>
          </div>
        </header>

        {/* Dynamic Route View */}
        <main className="min-w-0 flex-1 overflow-auto p-6 md:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
