"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { DEFAULT_ONBOARDING, OnboardingData, SERVICE_OPTIONS, STEPS, VOICE_OPTIONS } from "@/lib/onboarding-types";

const STORAGE_KEY = "owlbell_onboarding_v2";

function loadDraft(): OnboardingData {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULT_ONBOARDING, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return DEFAULT_ONBOARDING;
}

function saveDraft(data: OnboardingData) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(data)); } catch { /* ignore */ }
}

type StepKey = OnboardingData[keyof OnboardingData];

function validateStep(step: number, data: OnboardingData): string[] {
  const errors: string[] = [];
  const s = data[STEPS[step].key as keyof OnboardingData] as Record<string, unknown>;

  if (step === 0) {
    if (!s.companyName) errors.push("Company name is required");
    if (!s.ownerName) errors.push("Owner name is required");
    if (!s.email) errors.push("Email is required");
    if (!s.mobile) errors.push("Mobile number is required");
  }
  if (step === 1) {
    if (!s.serviceAreas) errors.push("Service areas are required");
  }
  if (step === 6) {
    if (!(s as OnboardingData["step7_aiVoice"]).voiceId) errors.push("Please select a voice");
  }

  return errors;
}

export default function OnboardingWizard() {
  const [step, setStep] = useState(0);
  const [data, setData] = useState<OnboardingData>(DEFAULT_ONBOARDING);
  const [errors, setErrors] = useState<string[]>([]);
  const [provisioning, setProvisioning] = useState(false);
  const [provisionDone, setProvisionDone] = useState(false);
  const isLastStep = step === STEPS.length - 1;

  useEffect(() => { setData(loadDraft()); }, []);

  useEffect(() => { saveDraft(data); }, [data]);

  const update = useCallback(<K extends keyof OnboardingData>(key: K, value: OnboardingData[K]) => {
    setData((prev) => ({ ...prev, [key]: value }));
    setErrors([]);
  }, []);

  const handleNext = useCallback(() => {
    const errs = validateStep(step, data);
    if (errs.length > 0) { setErrors(errs); return; }
    setErrors([]);
    if (isLastStep) {
      handleProvision();
    } else {
      setStep((s) => Math.min(s + 1, STEPS.length - 1));
    }
  }, [step, data, isLastStep]);

  const handleBack = useCallback(() => setStep((s) => Math.max(s - 1, 0)), []);

  const handleProvision = useCallback(async () => {
    setProvisioning(true);
    try {
      const res = await fetch("/api/onboarding/provision", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(data),
      });
      if (res.ok) {
        setProvisionDone(true);
        localStorage.removeItem(STORAGE_KEY);
      } else {
        setErrors(["Provisioning failed. Please try again or contact support."]);
      }
    } catch {
      setErrors(["Network error during provisioning. Please try again."]);
    } finally {
      setProvisioning(false);
    }
  }, [data]);

  const progress = ((step + 1) / STEPS.length) * 100;

  if (provisionDone) {
    return (
      <div className="onboarding-complete">
        <div className="onboarding-complete-icon">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="24" cy="24" r="20" /><path d="M16 24l6 6 10-10" />
          </svg>
        </div>
        <h2>Your receptionist build is ready for review.</h2>
        <p>Voice, call rules, routing, and tools are provisioned. Next step: test calls, tune the script, then forward client overflow.</p>
        <a href="/dashboard" className="btn btn--primary btn--lg">Go to Dashboard</a>
      </div>
    );
  }

  const currentKey = STEPS[step].key as keyof OnboardingData;
  const currentData = data[currentKey] as Record<string, unknown>;

  return (
    <div className="onboarding-wizard">
      <div className="onboarding-sidebar">
        <div className="onboarding-brand-panel">
          <a href="/" className="logo" aria-label="Owlbell home">
            <span className="logo-mark onboarding-logo-mark" aria-hidden />
            Owl<span>bell</span>
          </a>
          <p>Client setup built for real call quality: rules first, voice second, tuning always.</p>
        </div>
        <div className="onboarding-sidebar-steps">
          {STEPS.map((s, i) => (
            <button
              key={s.key}
              type="button"
              className={`onboarding-step-indicator${i === step ? " onboarding-step-indicator--active" : ""}${i < step ? " onboarding-step-indicator--done" : ""}`}
              onClick={() => i < step && setStep(i)}
              disabled={i > step}
            >
              <span className="onboarding-step-number">{i < step ? "✓" : i + 1}</span>
              <div className="onboarding-step-info">
                <div className="onboarding-step-label">{s.label}</div>
                <div className="onboarding-step-desc">{s.description}</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      <div className="onboarding-main">
        <div className="onboarding-progress-bar">
          <div className="onboarding-progress-fill" style={{ width: `${progress}%` }} />
        </div>

        <div className="onboarding-content">
          <div className="onboarding-topline">
            <span>Managed setup</span>
            <strong>Audit - configure - test - forward</strong>
          </div>
          <h2 className="onboarding-step-title">{STEPS[step].label}</h2>
          <p className="onboarding-step-subtitle">{STEPS[step].description}</p>

          {step === 0 && (
            <BusinessInfoStep data={currentData as OnboardingData["step1_businessInfo"]} onChange={(v) => update("step1_businessInfo", v)} />
          )}
          {step === 1 && (
            <BusinessDetailsStep data={currentData as OnboardingData["step2_businessDetails"]} onChange={(v) => update("step2_businessDetails", v)} />
          )}
          {step === 2 && (
            <CallHandlingStep data={currentData as OnboardingData["step3_callHandling"]} onChange={(v) => update("step3_callHandling", v)} />
          )}
          {step === 3 && (
            <CalendarStep data={currentData as OnboardingData["step4_calendar"]} onChange={(v) => update("step4_calendar", v)} />
          )}
          {step === 4 && (
            <KnowledgeBaseStep data={currentData as OnboardingData["step5_knowledgeBase"]} onChange={(v) => update("step5_knowledgeBase", v)} />
          )}
          {step === 5 && (
            <PhoneNumbersStep data={currentData as OnboardingData["step6_phoneNumbers"]} onChange={(v) => update("step6_phoneNumbers", v)} />
          )}
          {step === 6 && (
            <AiVoiceStep data={currentData as OnboardingData["step7_aiVoice"]} onChange={(v) => update("step7_aiVoice", v)} />
          )}
          {step === 7 && (
            <ReviewStep data={data} />
          )}

          {errors.length > 0 && (
            <div className="onboarding-errors">
              {errors.map((e, i) => <p key={i}>{e}</p>)}
            </div>
          )}
        </div>

        <div className="onboarding-footer">
          {step > 0 && (
            <button type="button" className="btn btn--ghost" onClick={handleBack} disabled={provisioning}>
              Back
            </button>
          )}
          <div className="onboarding-footer-right">
            <span className="onboarding-step-count">Step {step + 1} of {STEPS.length}</span>
            <button
              type="button"
              className="btn btn--primary btn--lg"
              onClick={handleNext}
              disabled={provisioning}
            >
              {provisioning ? "Building receptionist..." : isLastStep ? "Confirm Build" : "Continue"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function InputField({ label, value, onChange, placeholder, type = "text", optional }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string; type?: string; optional?: boolean;
}) {
  return (
    <label className="onboarding-field">
      <span className="onboarding-field-label">{label}{!optional && <span className="onboarding-required">*</span>}</span>
      {type === "textarea" ? (
        <textarea className="onboarding-input" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} rows={3} />
      ) : (
        <input className="onboarding-input" type={type} value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
      )}
    </label>
  );
}

function BusinessInfoStep({ data, onChange }: { data: OnboardingData["step1_businessInfo"]; onChange: (v: OnboardingData["step1_businessInfo"]) => void }) {
  const set = (key: keyof OnboardingData["step1_businessInfo"]) => (val: string) => onChange({ ...data, [key]: val });
  return (
    <div className="onboarding-fields">
      <InputField label="Company name" value={data.companyName} onChange={set("companyName")} placeholder="e.g. Acme Plumbing" />
      <InputField label="Owner name" value={data.ownerName} onChange={set("ownerName")} placeholder="e.g. John Smith" />
      <InputField label="Email" value={data.email} onChange={set("email")} type="email" placeholder="john@acmeplumbing.co.uk" />
      <InputField label="Mobile" value={data.mobile} onChange={set("mobile")} type="tel" placeholder="+44 7700 900000" />
      <InputField label="Business address" value={data.businessAddress} onChange={set("businessAddress")} placeholder="e.g. 123 High Street, London" />
      <InputField label="Website" value={data.website} onChange={set("website")} type="url" placeholder="https://acmeplumbing.co.uk" optional />
    </div>
  );
}

function BusinessDetailsStep({ data, onChange }: { data: OnboardingData["step2_businessDetails"]; onChange: (v: OnboardingData["step2_businessDetails"]) => void }) {
  const set = <K extends keyof OnboardingData["step2_businessDetails"]>(key: K) => (val: OnboardingData["step2_businessDetails"][K]) => onChange({ ...data, [key]: val });
  const toggleService = (svc: string) => {
    const next = data.servicesOffered.includes(svc)
      ? data.servicesOffered.filter((s) => s !== svc)
      : [...data.servicesOffered, svc];
    onChange({ ...data, servicesOffered: next });
  };
  return (
    <div className="onboarding-fields">
      <InputField label="Opening hours" value={data.openingHours} onChange={set("openingHours")} placeholder="e.g. Mon-Fri 8:00-17:00" />
      <label className="onboarding-field onboarding-field--checkbox">
        <input type="checkbox" checked={data.emergencyAvailable} onChange={(e) => set("emergencyAvailable")(e.target.checked)} />
        <span>24/7 emergency call availability</span>
      </label>
      <InputField label="Service areas" value={data.serviceAreas} onChange={set("serviceAreas")} placeholder="e.g. Greater London, Surrey, Kent" />
      <div className="onboarding-field">
        <span className="onboarding-field-label">Services offered</span>
        <div className="onboarding-chips">
          {SERVICE_OPTIONS.map((svc) => (
            <button key={svc} type="button" className={`onboarding-chip${data.servicesOffered.includes(svc) ? " onboarding-chip--active" : ""}`} onClick={() => toggleService(svc)}>
              {svc}
            </button>
          ))}
        </div>
      </div>
      <InputField label="Typical pricing info" value={data.typicalPricing} onChange={set("typicalPricing")} placeholder="e.g. £65 call-out + £85/hour" optional />
      <label className="onboarding-field">
        <span className="onboarding-field-label">Number of engineers</span>
        <input className="onboarding-input" type="number" min={1} max={100} value={data.numberOfEngineers} onChange={(e) => set("numberOfEngineers")(Math.max(1, parseInt(e.target.value) || 1))} />
      </label>
      <InputField label="Preferred greeting" value={data.preferredGreeting} onChange={set("preferredGreeting")} type="textarea" placeholder="Thanks for calling {company}, this is {name}. Are you calling about an emergency or would you like to book a visit?" />
    </div>
  );
}

function CallHandlingStep({ data, onChange }: { data: OnboardingData["step3_callHandling"]; onChange: (v: OnboardingData["step3_callHandling"]) => void }) {
  const set = <K extends keyof OnboardingData["step3_callHandling"]>(key: K) => (val: OnboardingData["step3_callHandling"][K]) => onChange({ ...data, [key]: val });
  return (
    <div className="onboarding-fields">
      <InputField label="Booking rules" value={data.bookingRules} onChange={set("bookingRules")} type="textarea" placeholder="e.g. Minimum 2 hours notice, no call-outs after 10pm unless emergency" />
      <label className="onboarding-field">
        <span className="onboarding-field-label">Emergency routing</span>
        <select className="onboarding-input" value={data.emergencyRouting} onChange={(e) => set("emergencyRouting")(e.target.value)}>
          <option value="escalate_emergency">Escalate to on-call team immediately</option>
          <option value="book_next_slot">Book next available slot</option>
          <option value="business_hours">Business hours only</option>
        </select>
      </label>
      <label className="onboarding-field">
        <span className="onboarding-field-label">Out-of-hours behaviour</span>
        <select className="onboarding-input" value={data.outOfHoursBehavior} onChange={(e) => set("outOfHoursBehavior")(e.target.value)}>
          <option value="voicemail">Take message and alert owner</option>
          <option value="emergency_only">Emergency calls only</option>
          <option value="transfer">Transfer to on-call number</option>
        </select>
      </label>
      <InputField label="Transfer numbers (comma separated)" value={data.transferNumbers.join(", ")} onChange={(v) => set("transferNumbers")(v.split(",").map((s) => s.trim()).filter(Boolean))} placeholder="+44 7700 900001, +44 7700 900002" optional />
      <InputField label="Voicemail preferences" value={data.voicemailPreferences} onChange={set("voicemailPreferences")} type="textarea" placeholder="e.g. Always take a callback number and reason for call" optional />
    </div>
  );
}

function CalendarStep({ data, onChange }: { data: OnboardingData["step4_calendar"]; onChange: (v: OnboardingData["step4_calendar"]) => void }) {
  const set = <K extends keyof OnboardingData["step4_calendar"]>(key: K) => (val: OnboardingData["step4_calendar"][K]) => onChange({ ...data, [key]: val });
  return (
    <div className="onboarding-fields">
      <label className="onboarding-field">
        <span className="onboarding-field-label">Calendar provider</span>
        <div className="onboarding-radio-group">
          {[["", "Skip for now"], ["google", "Google Calendar"], ["microsoft", "Microsoft 365"]].map(([val, label]) => (
            <button key={val} type="button" className={`onboarding-radio${data.provider === val ? " onboarding-radio--active" : ""}`} onClick={() => set("provider")(val as OnboardingData["step4_calendar"]["provider"])}>
              {label}
            </button>
          ))}
        </div>
      </label>
      {data.provider && (
        <>
          <label className="onboarding-field">
            <span className="onboarding-field-label">Appointment duration (minutes)</span>
            <input className="onboarding-input" type="number" min={15} max={240} step={15} value={data.appointmentDuration} onChange={(e) => set("appointmentDuration")(parseInt(e.target.value) || 60)} />
          </label>
          <label className="onboarding-field">
            <span className="onboarding-field-label">Buffer time between appointments (minutes)</span>
            <input className="onboarding-input" type="number" min={0} max={60} step={5} value={data.bufferTime} onChange={(e) => set("bufferTime")(parseInt(e.target.value) || 15)} />
          </label>
        </>
      )}
      <p className="onboarding-hint">Calendar sync lets Owlbell hold or book slots based on your rules. OAuth connection is completed after the initial build review.</p>
    </div>
  );
}

function KnowledgeBaseStep({ data, onChange }: { data: OnboardingData["step5_knowledgeBase"]; onChange: (v: OnboardingData["step5_knowledgeBase"]) => void }) {
  const set = (key: keyof OnboardingData["step5_knowledgeBase"]) => (val: string) => onChange({ ...data, [key]: val });
  return (
    <div className="onboarding-fields">
      <InputField label="FAQs (common questions and answers)" value={data.faqs} onChange={set("faqs")} type="textarea" placeholder="e.g. Q: Do you charge for call-outs? A: Yes, £65 call-out fee applies." optional />
      <InputField label="Price list" value={data.priceList} onChange={set("priceList")} type="textarea" placeholder="e.g. Boiler repair from £150, Tap replacement from £80" optional />
      <InputField label="Service information" value={data.serviceInfo} onChange={set("serviceInfo")} type="textarea" placeholder="Describe your services, guarantees, coverage area in detail" optional />
      <InputField label="Policies" value={data.policies} onChange={set("policies")} type="textarea" placeholder="e.g. Cancellation policy, warranty info, payment terms" optional />
      <InputField label="Website URL for auto-import" value={data.websiteUrl} onChange={set("websiteUrl")} type="url" placeholder="https://acmeplumbing.co.uk" optional />
      <p className="onboarding-hint">The AI will use this information to answer caller questions accurately. You can always update this later.</p>
    </div>
  );
}

function PhoneNumbersStep({ data, onChange }: { data: OnboardingData["step6_phoneNumbers"]; onChange: (v: OnboardingData["step6_phoneNumbers"]) => void }) {
  const set = <K extends keyof OnboardingData["step6_phoneNumbers"]>(key: K) => (val: OnboardingData["step6_phoneNumbers"][K]) => onChange({ ...data, [key]: val });
  return (
    <div className="onboarding-fields">
      <label className="onboarding-field">
        <span className="onboarding-field-label">Phone number type</span>
        <div className="onboarding-radio-group">
          <button type="button" className={`onboarding-radio${data.type === "new" ? " onboarding-radio--active" : ""}`} onClick={() => set("type")("new")}>
            Get a new business number
          </button>
          <button type="button" className={`onboarding-radio${data.type === "port" ? " onboarding-radio--active" : ""}`} onClick={() => set("type")("port")}>
            Port my existing number
          </button>
        </div>
      </label>
      {data.type === "new" ? (
        <InputField label="Desired number (optional)" value={data.desiredNumber} onChange={set("desiredNumber")} placeholder="e.g. 020 7946 0123" optional />
      ) : (
        <>
          <InputField label="Existing number to port" value={data.existingNumber} onChange={set("existingNumber")} placeholder="e.g. 020 7946 0123" />
          <label className="onboarding-field onboarding-field--checkbox">
            <input type="checkbox" checked={data.forwardingConfigured} onChange={(e) => set("forwardingConfigured")(e.target.checked)} />
            <span>I have access to the number and can verify ownership</span>
          </label>
        </>
      )}
    </div>
  );
}

function AiVoiceStep({ data, onChange }: { data: OnboardingData["step7_aiVoice"]; onChange: (v: OnboardingData["step7_aiVoice"]) => void }) {
  return (
    <div className="onboarding-fields">
      <span className="onboarding-field-label">Select a receptionist voice</span>
      <div className="onboarding-voice-list">
        {VOICE_OPTIONS.map((voice) => (
          <button
            key={voice.id}
            type="button"
            className={`onboarding-voice-card${data.voiceId === voice.id ? " onboarding-voice-card--active" : ""}`}
            onClick={() => onChange({ ...data, voiceId: voice.id, voiceName: voice.name })}
          >
            <div className="onboarding-voice-name">{voice.name}</div>
            <div className="onboarding-voice-style">{voice.style}</div>
          </button>
        ))}
      </div>
      <p className="onboarding-hint">Voice is only part of the result. The call script, pacing, escalation rules, and review loop are tuned after setup.</p>
    </div>
  );
}

function ReviewStep({ data }: { data: OnboardingData }) {
  const sections = [
    { label: "Business Info", fields: [
      ["Company", data.step1_businessInfo.companyName],
      ["Owner", data.step1_businessInfo.ownerName],
      ["Email", data.step1_businessInfo.email],
      ["Mobile", data.step1_businessInfo.mobile],
      ["Address", data.step1_businessInfo.businessAddress],
    ]},
    { label: "Business Details", fields: [
      ["Hours", data.step2_businessDetails.openingHours],
      ["Emergency", data.step2_businessDetails.emergencyAvailable ? "24/7 available" : "Business hours only"],
      ["Service areas", data.step2_businessDetails.serviceAreas],
      ["Engineers", String(data.step2_businessDetails.numberOfEngineers)],
    ]},
    { label: "Call Handling", fields: [
      ["Emergency routing", data.step3_callHandling.emergencyRouting],
      ["Out-of-hours", data.step3_callHandling.outOfHoursBehavior],
    ]},
    { label: "Voice", fields: [
      ["Voice", data.step7_aiVoice.voiceName || "Default"],
    ]},
  ];

  return (
    <div className="onboarding-review">
      {sections.map((section) => (
        <div key={section.label} className="onboarding-review-section">
          <h3>{section.label}</h3>
          {section.fields.filter(([, v]) => v).map(([label, value]) => (
            <div key={label} className="onboarding-review-row">
              <span className="onboarding-review-label">{label}</span>
              <span className="onboarding-review-value">{value}</span>
            </div>
          ))}
        </div>
      ))}
      <div className="onboarding-review-notice">
        After confirming, we build the receptionist draft automatically. Test calls and prompt tuning happen before forwarding client traffic.
      </div>
    </div>
  );
}
