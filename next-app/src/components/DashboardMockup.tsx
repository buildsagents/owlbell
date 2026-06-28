const FLOW = [
  { id: "ring", label: "Call rings", detail: "(303) 555-0187 · burst pipe emergency" },
  { id: "answer", label: "Agency answers", detail: "Script matched to your shop · 1.8s" },
  { id: "book", label: "Slot confirmed", detail: "Tomorrow 11:00 AM · Jake (lead tech)" },
  { id: "text", label: "You're notified", detail: "SMS to owner line with full summary" },
];

export default function DashboardMockup() {
  return (
    <section className="section call-flow" id="dashboard">
      <div className="wrap">
        <header className="section-lead section-lead--center">
          <p className="kicker kicker--dark">End to end</p>
          <h2>From ring to booked job — one thread</h2>
          <p>
            No full dashboard tour. This is the moment that matters: the call is handled,
            the calendar is updated, and you know about it immediately.
          </p>
        </header>

        <div className="call-flow-track" aria-label="Call handling flow">
          {FLOW.map((step, index) => (
            <article key={step.id} className="call-flow-step">
              <span className="call-flow-index num">{index + 1}</span>
              <h3>{step.label}</h3>
              <p>{step.detail}</p>
              {index < FLOW.length - 1 && <span className="call-flow-arrow" aria-hidden>→</span>}
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}