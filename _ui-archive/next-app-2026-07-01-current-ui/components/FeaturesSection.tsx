const FEATURES = [
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 3h16v10H2z" /><path d="M6 17h8" /><path d="M10 13v4" />
      </svg>
    ),
    label: "24/7 call answering",
    desc: "Nights, weekends, holidays - overflow calls get a calm answer instead of voicemail.",
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16z" /><path d="M10 6v6" /><path d="M7 10l3 3 3-3" />
      </svg>
    ),
    label: "Human-sounding triage",
    desc: "One question at a time, no robotic loops, no awkward over-talking, no fake enthusiasm.",
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="4" width="16" height="12" rx="2" /><path d="M6 8h8" /><path d="M6 11h5" />
      </svg>
    ),
    label: "Instant owner SMS",
    desc: "Job details land on your phone before the customer calls someone else - caller, issue, address, slot.",
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 2v4M12 2v4M4 10h12M4 14h12M4 6h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z" />
      </svg>
    ),
    label: "Booking and escalation rules",
    desc: "Qualified emergencies can be transferred, held for dispatch, or booked based on the client's rules.",
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z" /><path d="M10 10v4" /><path d="M10 6h.01" />
      </svg>
    ),
    label: "CRM / tool handoff",
    desc: "Booked jobs sync to Jobber, ServiceTitan, Housecall Pro, or arrive as structured data for your dispatcher.",
  },
  {
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 2L2 10l3 3 5-5 5 5 3-3-8-8z" />
      </svg>
    ),
    label: "Managed improvement loop",
    desc: "Call outcomes are reviewed and scripts are tuned so the receptionist keeps sounding sharper.",
  },
];

export default function FeaturesSection() {
  return (
    <section className="section" id="features">
      <div className="wrap">
        <div className="section-lead">
          <span className="section-label">Business outcomes</span>
          <h2>Every feature exists to win trust on the phone.</h2>
          <p>Cleaner calls, cleaner handoffs, and a setup process the client does not have to manage.</p>
        </div>
        <div className="features-grid">
          {FEATURES.map((f, i) => (
            <div key={i} className="feature">
              <div className="feature-icon">{f.icon}</div>
              <h3>{f.label}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
