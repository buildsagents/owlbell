const STEPS = [
  {
    id: "answer",
    title: "1 — Answered in Under 2 Seconds",
    description:
      "Agency-trained receptionists pick up instantly — scripted, tuned, and managed by our team.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M6.5 4.8c1.8-.9 4-.5 5.4 1.1 1.1 1.3 1.2 3.1.4 4.5"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M4.8 7.2C3.4 9.4 3.2 12.3 4.5 14.7c1.2 2.2 3.6 3.6 6.1 3.7"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M8.2 10.2c2.2 2.2 5.4 2.2 7.6 0M10.5 18.5 8.5 20.5 6 20.5a2 2 0 0 1-2-2v-1.5l2.2-2.2"
        />
      </svg>
    ),
  },
  {
    id: "triage",
    title: "2 — Qualified Like Your Best Dispatcher",
    description:
      "We ask the right questions, identify urgency, and route emergencies — overseen by real humans.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"
        />
        <path strokeLinecap="round" d="M9 5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2" />
        <path strokeLinecap="round" strokeLinejoin="round" d="m9 14 2 2 4-4" />
      </svg>
    ),
  },
  {
    id: "book",
    title: "3 — Booked on Your Calendar",
    description:
      "Appointments confirmed in real time with your availability rules — no double-books, no gaps.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M8 4v2m8-2v2M5 8h14M6 6h12a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2Z"
        />
        <path strokeLinecap="round" strokeLinejoin="round" d="m9 14 2 2 4-4" />
      </svg>
    ),
  },
  {
    id: "summary",
    title: "4 — You Stay in Control",
    description:
      "Instant text summaries with job details, so you walk into every call informed and ready.",
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M7 8.5h10M7 12h6M7 15.5h4"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M6 5h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-3 3V7a2 2 0 0 1 2-2Z"
        />
      </svg>
    ),
  },
];

export default function HowItWorksSection() {
  return (
    <section className="section section--alt" id="how">
      <div className="wrap">
        <header className="section-header">
          <span className="section-eyebrow">How the agency works</span>
          <h2>A Managed Reception Team — Without the Payroll</h2>
          <p>
            Owlbell is a done-for-you AI receptionist agency. We handle setup,
            scripting, and ongoing tuning so every call is answered, qualified,
            and booked like you hired a full-time front desk.
          </p>
        </header>

        <ol className="how-steps">
          {STEPS.map((step) => (
            <li key={step.id} className="how-step">
              <article className="how-step-card agency-card">
                <div className="how-step-icon">{step.icon}</div>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </article>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}