import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { ShieldCheck, LogIn } from "lucide-react";
import { useAuth, homeForRole } from "../lib/auth";
import { Button, Field, Input, Spinner } from "../components/ui";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const resp = await login(email.trim(), password);
      nav(homeForRole(resp.role), { replace: true });
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  function fillPoliceDemo() {
    setEmail("police@bengaluru.gov.in");
    setPassword("police123");
  }

  return (
    <AuthShell title="Sign in" subtitle="Tourist Safety Control Center">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email">
          <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                 placeholder="you@example.com" autoFocus />
        </Field>
        <Field label="Password">
          <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                 placeholder="••••••••" />
        </Field>
        {err && <p className="text-sm text-red-600">{err}</p>}
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? <Spinner /> : <LogIn size={16} />} Sign in
        </Button>
      </form>

      <button
        onClick={fillPoliceDemo}
        className="mt-3 w-full rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500 ring-1 ring-inset ring-slate-200 hover:bg-slate-100"
      >
        Use police demo login
      </button>

      <p className="mt-4 text-center text-sm text-slate-500">
        New tourist?{" "}
        <Link to="/signup" className="font-medium text-brand-600 hover:underline">
          Create an account
        </Link>
      </p>
    </AuthShell>
  );
}

export function AuthShell({ title, subtitle, children }) {
  return (
    <div className="flex min-h-full items-center justify-center bg-slate-100 p-6">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="grid h-12 w-12 place-items-center rounded-xl bg-brand-600 text-white">
            <ShieldCheck size={24} />
          </div>
          <h1 className="text-lg font-semibold text-slate-800">{title}</h1>
          <p className="text-sm text-slate-500">{subtitle}</p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          {children}
        </div>
      </div>
    </div>
  );
}
