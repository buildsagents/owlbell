"use client";

import { useMemo, useState } from "react";
import { FASTAPI_V1 } from "@/lib/consolidation";

/**
 * Post-checkout onboarding portal (concierge model). Collects the business
 * details the ops team provisions against, then hands off to a "we're building
 * your AI" confirmation. Premium, guided, one step at a time.
 */

type Intake = {
  email: string;
  businessName: string;
  trade: string;
  serviceArea: string;
  website: string;
  forwardNumber: string;
  numberChoice: string;
  hours: string;
  emergency: string;
  greeting: string;
  tone: string;
  topServices: string;
  doNot: string;
  faq: string;
  calendar: string;
  smsNumber: string;
  summaryEmail: string;
};

const PLUMBING_TRADE = "Plumbing";
const TONES = ["Warm & friendly", "Professional & efficient", "Calm & reassuring"];

const STEPS = [
  { key: "business", title: "Your plumbing company", hint: "The basics so your AI introduces your shop correctly." },
  { key: "calls", title: "Calls & hours", hint: "How calls reach you and when you're open." },
  { key: "ai", title: "Your AI receptionist", hint: "How it should sound and what to highlight." },
  { key: "knowledge", title: "Knowledge & FAQs", hint: "What callers ask — so it answers like you would." },
  { key: "integrations", title: "Calendar & alerts", hint: "Where bookings land and how you're notified." },
  { key: "review", title: "Review & submit", hint: "Confirm and we'll start building." },
] as const;

const EMPTY: Intake = {
  email: "", businessName: "", trade: PLUMBING_TRADE, serviceArea: "", website: "",
  forwardNumber: "", numberChoice: "new", hours: "", emergency: "yes",
  greeting: "", tone: TONES[0], topServices: "", doNot: "",
  faq: "", calendar: "google", smsNumber: "", summaryEmail: "",
};

export default function OnboardingPortal() {
  const [step, setStep] = useState(0);
  const [data, setData] = useState<Intake>(EMPTY);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  const set = (k: keyof Intake) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
    setData((d) => ({ ...d, [k]: e.target.value }));

  // Per-step required fields gate the "Continue" button.
  const canAdvance = useMemo(() => {
    switch (STEPS[step].key) {
      case "business":
        return data.businessName.trim() && data.email.trim() && data.serviceArea.trim();
      case "calls":
        return data.forwardNumber.trim() && data.hours.trim();
      case "ai":
        return data.greeting.trim() && data.topServices.trim();
      case "integrations":
        return data.smsNumber.trim();
      default:
        return true;
    }
  }, [step, data]);

  const pct = Math.round(((step + 1) / STEPS.length) * 100);

  const submit = async () => {
    setSubmitting(true);
    setError("");
    try {
      const sessionId = typeof window !== "undefined"
        ? new URLSearchParams(window.location.search).get("session_id")
        : null;
      const res = await fetch(`${FASTAPI_V1}/onboarding/intake`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...data, sessionId }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) throw new Error(json.error || "Could not submit");
      setDone(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <main className="ob-wrap">
        <div className="ob-card ob-done">
          <div className="ob-done-badge">🦉</div>
          <h1>You&apos;re all set, {data.businessName}.</h1>
          <p>
            Your dedicated specialist is configuring your AI receptionist now —
            building your knowledge base, connecting your number, and running test
            calls. <strong>You&apos;ll be live within ~1 business day</strong>, and
            we&apos;ll email <strong>{data.email}</strong> the moment it&apos;s ready.
          </p>
          <ul className="ob-next">
            <li>✅ Details received</li>
            <li>⏳ AI receptionist being configured</li>
            <li>⏳ Phone number connected & test calls</li>
            <li>⏳ Go live — we&apos;ll notify you</li>
          </ul>
          <p className="ob-muted">Questions? Email hello@owlbell.xyz — we reply in under 2 hours.</p>
        </div>
      </main>
    );
  }

  const s = STEPS[step].key;

  return (
    <main className="ob-wrap">
      <div className="ob-head">
        <div className="ob-logo">Owl<span>bell</span></div>
        <div className="ob-step-count">Step {step + 1} of {STEPS.length}</div>
      </div>

      <div className="ob-progress"><div className="ob-progress-bar" style={{ width: `${pct}%` }} /></div>

      <div className="ob-card">
        <div className="ob-card-head">
          <h1>{STEPS[step].title}</h1>
          <p>{STEPS[step].hint}</p>
        </div>

        {s === "business" && (
          <div className="ob-fields">
            <Field label="Business name *"><input value={data.businessName} onChange={set("businessName")} placeholder="Rapid Flow Plumbing" /></Field>
            <Field label="Email *" hint="Where we'll send your go-live notice"><input type="email" value={data.email} onChange={set("email")} placeholder="you@business.com" /></Field>
            <Field label="Service area *"><input value={data.serviceArea} onChange={set("serviceArea")} placeholder="Austin, TX + 30 mi" /></Field>
            <Field label="Website"><input value={data.website} onChange={set("website")} placeholder="rapidflowplumbing.com" /></Field>
          </div>
        )}

        {s === "calls" && (
          <div className="ob-fields">
            <Field label="Phone number to forward / your main line *"><input value={data.forwardNumber} onChange={set("forwardNumber")} placeholder="(512) 555-0100" /></Field>
            <Field label="Number setup">
              <select value={data.numberChoice} onChange={set("numberChoice")}>
                <option value="new">Give me a new Owlbell number</option>
                <option value="forward">Forward my existing number to Owlbell</option>
              </select>
            </Field>
            <Field label="Business hours *"><input value={data.hours} onChange={set("hours")} placeholder="Mon–Sat 7am–7pm" /></Field>
            <Field label="Handle emergency / after-hours calls?">
              <select value={data.emergency} onChange={set("emergency")}>
                <option value="yes">Yes — answer 24/7 and route urgent calls</option>
                <option value="no">No — only during business hours</option>
              </select>
            </Field>
          </div>
        )}

        {s === "ai" && (
          <div className="ob-fields">
            <Field label="Greeting * " hint="The first line callers hear">
              <input value={data.greeting} onChange={set("greeting")} placeholder="Thanks for calling Rapid Flow Plumbing, how can I help?" />
            </Field>
            <Field label="Tone"><select value={data.tone} onChange={set("tone")}>{TONES.map((t) => <option key={t}>{t}</option>)}</select></Field>
            <Field label="Top services to mention / book *"><textarea value={data.topServices} onChange={set("topServices")} rows={3} placeholder="Leak repair, drain cleaning, water heaters, emergency plumbing" /></Field>
            <Field label="Anything it should NOT do" hint="Optional"><textarea value={data.doNot} onChange={set("doNot")} rows={2} placeholder="Don't quote exact prices — book an estimate instead" /></Field>
          </div>
        )}

        {s === "knowledge" && (
          <div className="ob-fields">
            <Field label="Common questions & answers" hint="Pricing, service area, guarantees, payment — anything callers ask">
              <textarea value={data.faq} onChange={set("faq")} rows={7} placeholder={"Do you offer free estimates? — Yes, always free.\nWhat areas do you serve? — Austin + 30 miles.\nDo you charge after hours? — A small emergency fee applies."} />
            </Field>
          </div>
        )}

        {s === "integrations" && (
          <div className="ob-fields">
            <Field label="Calendar">
              <select value={data.calendar} onChange={set("calendar")}>
                <option value="google">Google Calendar</option>
                <option value="outlook">Outlook</option>
                <option value="none">No calendar yet — text me bookings</option>
              </select>
            </Field>
            <Field label="Mobile number for booking texts *"><input value={data.smsNumber} onChange={set("smsNumber")} placeholder="(512) 555-0199" /></Field>
            <Field label="Email for call summaries" hint="Optional — defaults to your account email"><input type="email" value={data.summaryEmail} onChange={set("summaryEmail")} placeholder="you@business.com" /></Field>
          </div>
        )}

        {s === "review" && (
          <div className="ob-review">
            <Row k="Plumbing company" v={data.businessName} />
            <Row k="Service area" v={data.serviceArea} />
            <Row k="Email" v={data.email} />
            <Row k="Number" v={`${data.forwardNumber} · ${data.numberChoice === "new" ? "new Owlbell number" : "forward existing"}`} />
            <Row k="Hours" v={`${data.hours}${data.emergency === "yes" ? " · 24/7 emergency" : ""}`} />
            <Row k="Greeting" v={data.greeting} />
            <Row k="Tone" v={data.tone} />
            <Row k="Top services" v={data.topServices} />
            {data.doNot && <Row k="Avoid" v={data.doNot} />}
            {data.faq && <Row k="FAQs" v={`${data.faq.split("\n").filter(Boolean).length} provided`} />}
            <Row k="Calendar" v={data.calendar} />
            <Row k="Booking texts to" v={data.smsNumber} />
            {error && <p className="ob-error">{error}</p>}
          </div>
        )}

        <div className="ob-actions">
          {step > 0 && <button className="btn btn-ghost" onClick={() => setStep((n) => n - 1)} disabled={submitting}>← Back</button>}
          {s !== "review" ? (
            <button className="btn btn-primary" onClick={() => setStep((n) => n + 1)} disabled={!canAdvance}>Continue →</button>
          ) : (
            <button className="btn btn-primary" onClick={submit} disabled={submitting}>
              {submitting ? "Submitting…" : "Submit & start building →"}
            </button>
          )}
        </div>
      </div>

      <p className="ob-foot">🔒 Your details are used only to configure your AI receptionist.</p>
    </main>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="ob-field">
      <span className="ob-field-label">{label}{hint && <em> · {hint}</em>}</span>
      {children}
    </label>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="ob-row">
      <span className="ob-row-k">{k}</span>
      <span className="ob-row-v">{v}</span>
    </div>
  );
}
