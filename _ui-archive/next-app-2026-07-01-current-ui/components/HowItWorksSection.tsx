import Link from "next/link";

const HOW_STEPS = [
  {
    label: "We audit missed-call value",
    desc: "We estimate lost after-hours revenue, emergency volume, and the first call flows worth automating.",
  },
  {
    label: "We build the receptionist",
    desc: "Voice, greeting, emergency script, transfer rules, booking logic, and owner SMS are configured for the client.",
  },
  {
    label: "The client forwards overflow",
    desc: "They point after-hours or missed calls to Owlbell. No app rollout, no staff retraining, no technical lift.",
  },
  {
    label: "We tune from real calls",
    desc: "Every call summary shows what happened. We tighten prompts and routing until the receptionist sounds natural.",
  },
];

export default function HowItWorksSection() {
  return (
    <section className="section" id="how-it-works">
      <div className="wrap">
        <div className="section-lead">
          <span className="section-label">How it works</span>
          <h2>Set up for clients without chaos.</h2>
          <p>The agency delivery system is simple: audit, configure, forward, tune.</p>
        </div>
        <div className="steps">
          {HOW_STEPS.map((step, i) => (
            <div key={i} className="step">
              <div className="step-num">{i + 1}</div>
              <h3>{step.label}</h3>
              <p>{step.desc}</p>
            </div>
          ))}
        </div>
        <div style={{ textAlign: "center", marginTop: "40px" }}>
          <Link href="/onboarding?source=how" className="btn btn--primary">
            Book a Demo
          </Link>
        </div>
      </div>
    </section>
  );
}
