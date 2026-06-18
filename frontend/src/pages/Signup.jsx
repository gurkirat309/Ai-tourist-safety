import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { UserPlus } from "lucide-react";
import { useAuth, homeForRole } from "../lib/auth";
import { Button, Field, Input, Spinner } from "../components/ui";
import { AuthShell } from "./Login";

export default function Signup() {
  const { signup } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({
    email: "",
    password: "",
    display_name: "",
    nationality: "",
    emergency_contact: "",
    consent_given: true,
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    if (!form.consent_given) {
      setErr("Consent is required to use safety monitoring.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const resp = await signup({
        email: form.email.trim(),
        password: form.password,
        display_name: form.display_name || null,
        nationality: form.nationality || null,
        emergency_contact: form.emergency_contact || null,
        consent_given: form.consent_given,
        consent_purpose: "safety_monitoring",
      });
      nav(homeForRole(resp.role), { replace: true });
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title="Create your account" subtitle="Tourist registration (with consent)">
      <form onSubmit={submit} className="space-y-4">
        <Field label="Email">
          <Input type="email" value={form.email} onChange={set("email")} required />
        </Field>
        <Field label="Password" hint="At least 6 characters">
          <Input type="password" value={form.password} onChange={set("password")} required />
        </Field>
        <Field label="Name">
          <Input value={form.display_name} onChange={set("display_name")} placeholder="Aarav Sharma" />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Nationality">
            <Input value={form.nationality} onChange={set("nationality")} placeholder="IN" />
          </Field>
          <Field label="Emergency contact">
            <Input value={form.emergency_contact} onChange={set("emergency_contact")} placeholder="+91-…" />
          </Field>
        </div>
        <label className="flex items-start gap-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={form.consent_given}
            onChange={(e) => setForm({ ...form, consent_given: e.target.checked })}
            className="mt-0.5 h-4 w-4 accent-brand-600"
          />
          <span>I consent to processing my location for <b>safety monitoring</b> (DPDP).</span>
        </label>
        {err && <p className="text-sm text-red-600">{err}</p>}
        <Button type="submit" disabled={busy} className="w-full">
          {busy ? <Spinner /> : <UserPlus size={16} />} Create account
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-slate-500">
        Already have an account?{" "}
        <Link to="/login" className="font-medium text-brand-600 hover:underline">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
