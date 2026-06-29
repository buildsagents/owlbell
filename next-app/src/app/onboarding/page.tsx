"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { FASTAPI_V1 } from "@/lib/consolidation";
import { VERTICALS, type VerticalSlug } from "@/lib/verticals";
import {
  clearDraft,
  defaultDraft,
  loadDraft,
  saveDraft,
  type OnboardingDraft,
} from "@/lib/onboarding-storage";
import { canAdvanceStep, defaultGreetingForVertical } from "@/lib/onboarding-validation";
import { loadDraftRemote, saveDraftRemote } from "@/lib/onboarding-draft-api";

const STEPS = [
  { key: "business", title: "Your business", hint: "Basics so your AI introduces your shop correctly." },
  { key: "calls", title: "Calls & hours", hint: "Phone routing, hours, and emergency rules." },
  { key: "ai", title: "Voice & personality", hint: "How callers experience your AI receptionist." },
  { key: "knowledge", title: "Knowledge base", hint: "Scripts, FAQs, and optional document uploads." },
  { key: "integrations", title: "Calendar, CRM & alerts", hint: "Where bookings land and how you're notified." },
  { key: "pricing", title: "Choose your plan", hint: "Transparent tiers — self-serve selectable." },
  { key: "review", title: "Review & activate", hint: "Confirm and go live in minutes." },
] as const;

const VOICES = [
  { id: "warm_professional", label: "Warm professional" },
  { id: "calm_reassuring", label: "Calm & reassuring" },
  { id: "energetic_friendly", label: "Energetic & friendly" },
];

const CRM_OPTIONS = [
  { id: "none", label: "None yet" },
  { id: "jobber", label: "Jobber" },
  { id: "servicetitan", label: "ServiceTitan" },
  { id: "housecall", label: "Housecall Pro" },
  { id: "other", label: "Other / webhook" },
];

const PRICING_TIERS = [
  { id: "launch", label: "Launch", price: "$1,497/mo", note: "24/7 answering + emergency routing" },
  { id: "growth", label: "Growth", price: "$4,997/mo", note: "Calendar booking + CRM handoff (recommended)" },
  { id: "scale", label: "Scale", price: "$9,997+/mo", note: "Multi-location + dedicated success" },
];

function readQueryDefaults(): Partial<OnboardingDraft> {
  if (typeof window === "undefined") return {};
  const q = new URLSearchParams(window.location.search);
  const patch: Partial<OnboardingDraft> = {};
  if (q.get("vertical") && VERTICALS.some((v) => v.slug === q.get("vertical"))) {
    patch.vertical = q.get("vertical") as VerticalSlug;
  }
  if (q.get("missed")) patch.callsPerWeek = q.get("missed")!;
  if (q.get("job_value")) patch.avgTicket = q.get("job_value")!;
  if (q.get("recovered")) patch.roiAnnualRecovery = Number(q.get("recovered")) * 12;
  if (q.get("source")) patch.kbNotes = `Lead source: ${q.get("source")}`;
  return patch;
}

export default function OnboardingPortal() {
  const [step, setStep] = useState(0);
  const [data, setData] = useState<OnboardingDraft>(defaultDraft);
  const [submitting, setSubmitting] = useState(false);
  const [activated, setActivated] = useState(false);
  const [inboundLine, setInboundLine] = useState<string | null>(null);
  const [forwardLine, setForwardLine] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [hydrated, setHydrated] = useState(false);
  const [provisionMode, setProvisionMode] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const q = new URLSearchParams(window.location.search);
      const remote = await loadDraftRemote({
        draftId: q.get("draft_id") || undefined,
        email: q.get("email") || undefined,
      });
      const local = loadDraft();
      const base = remote
        ? { ...defaultDraft(), ...remote.draft }
        : { ...defaultDraft(), ...local };
      const draft = { ...base, ...readQueryDefaults() };
      if (remote?.draftId) draft.draftId = remote.draftId;
      setData(draft);
      setStep(remote?.step ?? draft.step);
      setHydrated(true);
    })();
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    saveDraft({ ...data, step });
  }, [data, step, hydrated]);

  useEffect(() => {
    if (!hydrated || !data.email.trim()) return;
    const timer = setTimeout(async () => {
      const id = await saveDraftRemote({ ...data, step }, data.draftId);
      if (id && id !== data.draftId) {
        setData((d) => ({ ...d, draftId: id }));
      }
    }, 900);
    return () => clearTimeout(timer);
  }, [data, step, hydrated]);

  const set = useCallback(
    (k: keyof OnboardingDraft) =>
      (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
        const val =
          e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value;
        setData((d) => ({ ...d, [k]: val }));
      },
    [],
  );

  const onVerticalChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const vertical = e.target.value as VerticalSlug;
    setData((d) => ({
      ...d,
      vertical,
      kbNotes: d.kbNotes || VERTICALS.find((v) => v.slug === vertical)?.sampleServices || "",
    }));
  };

  const onKbFiles = (e: React.ChangeEvent<HTMLInputElement>) => {
    const names = Array.from(e.target.files || []).map((f) => f.name);
    setData((d) => ({ ...d, kbFileNames: [...d.kbFileNames, ...names] }));
  };

  const stepKey = STEPS[step].key;
  const canAdvance = useMemo(
    () => canAdvanceStep(stepKey, data as unknown as Record<string, string | boolean | string[]>),
    [stepKey, data],
  );

  const pct = Math.round(((step + 1) / STEPS.length) * 100);

  const submit = async () => {
    setSubmitting(true);
    setError("");
    try {
      const sessionId =
        typeof window !== "undefined"
          ? new URLSearchParams(window.location.search).get("session_id")
          : null;
      const greeting =
        data.kbNotes.includes("Thanks for calling") || data.kbNotes.includes("Thank you for calling")
          ? data.kbNotes.split("\n")[0]
          : defaultGreetingForVertical(data.vertical, data.businessName);

      // Inbound/test line is server-assigned on activation (derive_sandbox_inbound_line).
      // Client sends forwardNumber + numberChoice only; response returns inbound_line + forward_line.
      const payload = {
        email: data.email,
        businessName: data.businessName,
        trade: VERTICALS.find((v) => v.slug === data.vertical)?.trade || "Service",
        serviceArea: data.serviceArea,
        website: data.website,
        forwardNumber: data.forwardNumber,
        numberChoice: data.phoneSetup === "new_number" ? "new" : "forward",
        hours: data.businessHours,
        emergency: data.emergencyRouting.includes("24") ? "yes" : "yes",
        greeting,
        tone: data.personality,
        voiceId: data.voiceId,
        topServices: data.kbNotes,
        faq: data.kbNotes,
        calendar: data.calendarProvider,
        crmProvider: data.crmProvider,
        smsNumber: data.smsNotify ? data.smsNumber || data.email : "",
        pricingTier: data.pricingTier,
        kbFileNames: data.kbFileNames,
        selfServe: true,
        sessionId,
      };

      const res = await fetch(`${FASTAPI_V1}/onboarding/intake`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) throw new Error(json.error || json.detail || "Could not submit");
      setInboundLine(json.inbound_line || json.test_call_number || null);
      setForwardLine(json.forward_line || data.forwardNumber || null);
      setProvisionMode(json.provision_mode || null);
      setActivated(Boolean(json.activated));
      clearDraft();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  };

  if (!hydrated) {
    return (
      <main className="ob-wrap">
        <div className="ob-card">Loading your progress…</div>
      </main>
    );
  }

  if (activated) {
    return (
      <main className="ob-wrap">
        <div className="ob-card ob-done">
          <div className="ob-done-badge">🦉</div>
          <h1>Your AI is live, {data.businessName}.</h1>
          <p>
            {provisionMode === "retell"
              ? "Your Retell agent is provisioned. Call your Owlbell inbound line below to hear your configured AI."
              : "Sandbox mode: your configuration is saved and a dedicated inbound line is reserved. Use the interactive web sandbox for an immediate voice test, or dial inbound once forwarding is live."}
          </p>
          <ul className="ob-next">
            <li>✅ AI personality & voice configured</li>
            <li>✅ Knowledge base received</li>
            <li>✅ Calendar & CRM preferences saved</li>
            <li>✅ {PRICING_TIERS.find((t) => t.id === data.pricingTier)?.label || "Growth"} plan selected</li>
          </ul>
          <div className="ob-actions ob-actions--center">
            {provisionMode === "retell" && inboundLine ? (
              <a href={`tel:${inboundLine.replace(/\D/g, "")}`} className="btn btn--copper">
                Place first test call
              </a>
            ) : (
              <Link
                href={`/demo?vertical=${data.vertical}&source=activation`}
                className="btn btn--copper"
              >
                Test your AI in web sandbox
              </Link>
            )}
            {!inboundLine && provisionMode === "retell" && (
              <p className="ob-error">Activation did not return an inbound line — contact support or retry.</p>
            )}
          </div>
          {inboundLine && (
            <p className="ob-muted">
              Reserved inbound line (server-assigned from your email): <strong>{inboundLine}</strong>
              {forwardLine && (
                <>
                  {" "}
                  · Your main line to forward: <strong>{forwardLine}</strong>
                </>
              )}
              {" "}
              ·{" "}
              {provisionMode === "retell"
                ? "PSTN calls on this line reach your live Retell agent with your configured scripts."
                : "Sandbox PSTN does not answer until carrier forwarding is live — use the web sandbox above for an immediate voice preview with your settings."}
              {" "}
              · Dashboard access emailed to {data.email}
            </p>
          )}
        </div>
      </main>
    );
  }

  const s = stepKey;

  return (
    <main className="ob-wrap">
      <div className="ob-head">
        <div className="ob-logo">
          Owl<span>bell</span>
        </div>
        <div className="ob-step-count">
          Step {step + 1} of {STEPS.length} · saved to this device &amp; cloud
          {data.draftId && (
            <span className="ob-muted">
              {" "}
              · Resume link: /onboarding?draft_id={data.draftId}
            </span>
          )}
        </div>
      </div>

      <div className="ob-progress">
        <div className="ob-progress-bar" style={{ width: `${pct}%` }} />
      </div>

      <div className="ob-card">
        <div className="ob-card-head">
          <h1>{STEPS[step].title}</h1>
          <p>{STEPS[step].hint}</p>
        </div>

        {s === "business" && (
          <div className="ob-fields">
            <Field label="Business name *">
              <input value={data.businessName} onChange={set("businessName")} placeholder="Rapid Flow Plumbing" />
            </Field>
            <Field label="Email *" hint="Go-live notice + dashboard login">
              <input type="email" value={data.email} onChange={set("email")} placeholder="you@business.com" />
            </Field>
            <Field label="Vertical *">
              <select value={data.vertical} onChange={onVerticalChange}>
                {VERTICALS.map((v) => (
                  <option key={v.slug} value={v.slug}>
                    {v.trade}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Service area *">
              <input value={data.serviceArea} onChange={set("serviceArea")} placeholder="Austin, TX + 30 mi" />
            </Field>
            <Field label="Website">
              <input value={data.website} onChange={set("website")} placeholder="yourbusiness.com" />
            </Field>
          </div>
        )}

        {s === "calls" && (
          <div className="ob-fields">
            <Field label="Phone setup *">
              <select value={data.phoneSetup} onChange={set("phoneSetup")}>
                <option value="forward_existing">Forward my existing number to Owlbell</option>
                <option value="new_number">Provision a new Owlbell number</option>
              </select>
            </Field>
            <Field label="Main line / forward target *">
              <input value={data.forwardNumber} onChange={set("forwardNumber")} placeholder="(512) 555-0100" />
            </Field>
            <Field label="Business hours *">
              <input value={data.businessHours} onChange={set("businessHours")} placeholder="Mon–Sat 7am–7pm" />
            </Field>
            <Field label="Emergency routing *">
              <select value={data.emergencyRouting} onChange={set("emergencyRouting")}>
                <option value="escalate_emergency">24/7 — flag emergencies + SMS on-call</option>
                <option value="book_next_slot">Book next available slot only</option>
                <option value="business_hours">Business hours only</option>
              </select>
            </Field>
            <p className="ob-tip">💡 Tip: {VERTICALS.find((v) => v.slug === data.vertical)?.painPoints[0]}</p>
          </div>
        )}

        {s === "ai" && (
          <div className="ob-fields">
            <Field label="AI voice *">
              <select value={data.voiceId} onChange={set("voiceId")}>
                {VOICES.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Personality *">
              <select value={data.personality} onChange={set("personality")}>
                <option value="friendly_expert">Friendly expert</option>
                <option value="professional_efficient">Professional & efficient</option>
                <option value="calm_reassuring">Calm & reassuring</option>
              </select>
            </Field>
            <Field label="Preview greeting">
              <input
                readOnly
                value={defaultGreetingForVertical(data.vertical, data.businessName)}
              />
            </Field>
          </div>
        )}

        {s === "knowledge" && (
          <div className="ob-fields">
            <Field label="Services, scripts & FAQs" hint="One per line — or paste your price sheet">
              <textarea
                value={data.kbNotes}
                onChange={set("kbNotes")}
                rows={7}
                placeholder={
                  VERTICALS.find((v) => v.slug === data.vertical)?.sampleServices ||
                  "List services, FAQs, and booking rules"
                }
              />
            </Field>
            <Field label="Upload PDFs or docs (optional)">
              <input type="file" accept=".pdf,.doc,.docx,.txt" multiple onChange={onKbFiles} />
              {data.kbFileNames.length > 0 && (
                <span className="ob-muted">{data.kbFileNames.join(", ")} queued for indexing</span>
              )}
            </Field>
          </div>
        )}

        {s === "integrations" && (
          <div className="ob-fields">
            <Field label="Calendar">
              <select value={data.calendarProvider} onChange={set("calendarProvider")}>
                <option value="google">Google Calendar</option>
                <option value="outlook">Outlook / Microsoft 365</option>
                <option value="none">No calendar — text me bookings</option>
              </select>
            </Field>
            <Field label="CRM handoff">
              <select value={data.crmProvider} onChange={set("crmProvider")}>
                {CRM_OPTIONS.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="SMS booking alerts">
              <label className="ob-check">
                <input type="checkbox" checked={data.smsNotify} onChange={set("smsNotify")} />
                Text me when a job is booked
              </label>
            </Field>
            {data.smsNotify && (
              <Field label="Mobile number for alerts *">
                <input value={data.smsNumber} onChange={set("smsNumber")} placeholder="(512) 555-0199" />
              </Field>
            )}
          </div>
        )}

        {s === "pricing" && (
          <div className="ob-fields ob-pricing-pick">
            {PRICING_TIERS.map((tier) => (
              <label key={tier.id} className={`ob-pricing-option${data.pricingTier === tier.id ? " ob-pricing-option--on" : ""}`}>
                <input
                  type="radio"
                  name="pricingTier"
                  value={tier.id}
                  checked={data.pricingTier === tier.id}
                  onChange={set("pricingTier")}
                />
                <span className="ob-pricing-name">{tier.label}</span>
                <span className="ob-pricing-price">{tier.price}</span>
                <span className="ob-pricing-note">{tier.note}</span>
              </label>
            ))}
            <p className="ob-muted">Annual billing saves 15%. Founding sprint credit applied at checkout when eligible.</p>
          </div>
        )}

        {s === "review" && (
          <div className="ob-review">
            <Row k="Business" v={data.businessName} />
            <Row k="Vertical" v={VERTICALS.find((v) => v.slug === data.vertical)?.trade || data.vertical} />
            <Row k="Email" v={data.email} />
            <Row k="Phone setup" v={data.phoneSetup} />
            <Row k="Hours" v={data.businessHours} />
            <Row k="Voice" v={data.voiceId} />
            <Row k="CRM" v={data.crmProvider} />
            <Row k="Plan" v={data.pricingTier} />
            {error && <p className="ob-error">{error}</p>}
          </div>
        )}

        <div className="ob-actions">
          {step > 0 && (
            <button className="btn btn--outline" onClick={() => setStep((n) => n - 1)} disabled={submitting}>
              ← Back
            </button>
          )}
          {s !== "review" ? (
            <button className="btn btn--copper" onClick={() => setStep((n) => n + 1)} disabled={!canAdvance}>
              Continue
            </button>
          ) : (
            <button className="btn btn--copper" onClick={submit} disabled={submitting}>
              {submitting ? "Activating…" : "Activate my AI receptionist"}
            </button>
          )}
        </div>
      </div>

      <p className="ob-foot">🔒 TCPA-aware disclosures · encrypted at rest · resume anytime on any device</p>
    </main>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="ob-field">
      <span className="ob-field-label">
        {label}
        {hint && <em> · {hint}</em>}
      </span>
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