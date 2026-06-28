const STEPS = [
  {
    id: "answer",
    label: "We answer",
    detail:
      "Your line forwards to Owlbell. Our agency-trained receptionist picks up in under two seconds — nights, weekends, and lunch rush included.",
  },
  {
    id: "book",
    label: "We book",
    detail:
      "Emergencies get flagged. Standard jobs land on your calendar with your availability rules — no double-books.",
  },
  {
    id: "notify",
    label: "You get the text",
    detail:
      "A plain-English summary hits your phone: caller name, issue, time slot, and estimated job value. Review on your schedule.",
  },
];

export default function HowItWorksSection() {
  return (
    <section className="section section--warm" id="how">
      <div className="wrap">
        <header className="section-lead">
          <p className="kicker kicker--dark">Agency model</p>
          <h2>Three things happen on every call</h2>
          <p>Human-led setup. Ongoing script tuning. You never configure a dashboard on day one.</p>
        </header>

        <ol className="flow-steps">
          {STEPS.map((step, index) => (
            <li key={step.id} className="flow-step">
              <span className="flow-step-num num">{String(index + 1).padStart(2, "0")}</span>
              <div>
                <h3>{step.label}</h3>
                <p>{step.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}