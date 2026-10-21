/**
 * The screen a tourist actually lives on: current safety state, the tracking
 * switch, SOS, and the AI voice call.
 */
import { useEffect, useState } from "react";
import {
  Play,
  Square,
  Send,
  PhoneCall,
  TriangleAlert,
  Info,
  CheckCircle2,
  ShieldAlert,
} from "lucide-react";
import { useTracking } from "../lib/tracking";
import { api } from "../lib/api";
import { getSync, set, KEYS } from "../lib/storage";
import { Card, Button, Banner, Input, Field, Sheet } from "../components/ui";
import StatusCard from "../components/StatusCard";
import SosButton from "../components/SosButton";
import Advisories from "../components/Advisories";
import RiskForecast from "../components/RiskForecast";

export default function Home() {
  const {
    status, tracking, mode, fix, startGps, stop, sendNow, panic,
    geoMessage, lastSentAt, sending, online,
  } = useTracking();

  const [busy, setBusy] = useState(null);
  const [err, setErr] = useState(null);
  const [notice, setNotice] = useState(null);
  const [callOpen, setCallOpen] = useState(false);
  // Prefer the live fix; fall back to the last position the backend holds.
  const here = fix || status?.last_position || null;
  const [phone, setPhone] = useState(() => getSync(KEYS.phone, ""));

  // Clear transient notices so they don't linger across screens.
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(null), 8000);
    return () => clearTimeout(t);
  }, [notice]);

  async function toggleTracking() {
    setErr(null);
    if (tracking) {
      stop();
      return;
    }
    setBusy("track");
    try {
      const ok = await startGps();
      if (ok) setNotice("Tracking started. Your location is being shared.");
    } finally {
      setBusy(null);
    }
  }

  async function handleSendNow() {
    setBusy("send");
    setErr(null);
    try {
      await sendNow();
      setNotice("Location sent.");
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  }

  async function handlePanic() {
    setBusy("panic");
    setErr(null);
    try {
      const res = await panic();
      setNotice(
        res?.approximate
          ? "SOS sent using your last known location — GPS was unavailable. Stay put if you can."
          : "SOS sent. Authorities have your location and an officer is reviewing it."
      );
    } catch (e) {
      setErr(
        e.message ||
          "SOS could not be sent. If you are in danger, call 112 directly."
      );
    } finally {
      setBusy(null);
    }
  }

  async function handleCall() {
    const p = phone.trim();
    if (p.length < 8) {
      setErr("Enter a valid phone number, e.g. +91 9876543210.");
      return;
    }
    setBusy("call");
    setErr(null);
    try {
      set(KEYS.phone, p);
      const res = await api.requestVoiceCall({ phone_number: p });
      setCallOpen(false);
      setNotice(`Calling ${res.phone || p} — answer your phone when it rings.`);
    } catch (e) {
      setErr(e.message || "Could not start the call.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-3.5 p-4">
      {geoMessage && (
        <Banner tone="amber" icon={TriangleAlert}>
          {geoMessage}
        </Banner>
      )}
      {err && (
        <Banner tone="rose" icon={ShieldAlert}>
          {err}
        </Banner>
      )}
      {notice && (
        <Banner tone="emerald" icon={CheckCircle2}>
          {notice}
        </Banner>
      )}

      <StatusCard
        status={status}
        tracking={tracking}
        mode={mode}
        lastSentAt={lastSentAt}
      />

      <Advisories refreshKey={status?.last_seen} />

      {here && <RiskForecast lat={here.lat} lon={here.lon} title="Risk here today" />}

      {/* Tracking controls */}
      <Card className="p-4">
        <div className="flex items-center gap-2.5">
          <Button
            variant={tracking ? "subtle" : "primary"}
            icon={tracking ? Square : Play}
            busy={busy === "track"}
            onClick={toggleTracking}
            full
          >
            {tracking ? "Stop sharing" : "Start sharing location"}
          </Button>
          <Button
            variant="subtle"
            icon={Send}
            busy={busy === "send" || sending}
            onClick={handleSendNow}
            aria-label="Send location once"
            className="shrink-0 px-4"
          >
            Now
          </Button>
        </div>

        {fix && (
          <p className="mt-2.5 text-center text-[11px] text-slate-500">
            {fix.lat.toFixed(5)}, {fix.lon.toFixed(5)}
            {fix.accuracy_m != null && ` · ±${Math.round(fix.accuracy_m)} m`}
            {!online && " · offline"}
          </p>
        )}
      </Card>

      {/* Emergency */}
      <Card className="p-5">
        <div className="mb-4 flex items-center gap-2">
          <ShieldAlert size={16} className="text-rose-600" />
          <h3 className="text-[14px] font-bold text-slate-900">Emergency</h3>
        </div>

        <SosButton onFire={handlePanic} busy={busy === "panic"} />

        <div className="mt-5 border-t border-slate-100 pt-4">
          <Button
            variant="dark"
            icon={PhoneCall}
            full
            onClick={() => setCallOpen(true)}
          >
            Request AI assistance call
          </Button>
          <p className="mt-2 text-center text-[11px] leading-relaxed text-slate-500">
            An AI assistant calls your phone, checks on you, and passes what you
            say to the control room.
          </p>
        </div>
      </Card>

      <Banner tone="slate" icon={Info}>
        Alerts here are decision support for human officers — nothing is
        dispatched automatically. In immediate danger, call <b>112</b>.
      </Banner>

      <Sheet open={callOpen} onClose={() => setCallOpen(false)} title="AI assistance call">
        <div className="space-y-4">
          <p className="text-[13px] leading-relaxed text-slate-600">
            We'll call this number now. Answer and speak normally — the
            assistant will ask what's happening and share it with the control
            room along with your location.
          </p>
          <Field label="Your phone number" hint="Include the country code.">
            <Input
              type="tel"
              inputMode="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+91 9876543210"
            />
          </Field>
          <Button
            variant="danger"
            icon={PhoneCall}
            full
            busy={busy === "call"}
            onClick={handleCall}
          >
            Call me now
          </Button>
        </div>
      </Sheet>
    </div>
  );
}
