"use client";

const TIMELINE = [
  { time: "11:04 PM", event: "Inbound call — burst pipe, basement flooding" },
  { time: "11:04 PM", event: "Answered in 1.8s, emergency flagged" },
  { time: "11:06 PM", event: "Booked for 11:00 AM with lead tech" },
  { time: "11:06 PM", event: "Owner texted job summary + caller number" },
  { time: "11:00 AM", event: "Tech on site — $850 repair closed" },
];

export default function ProofResultsSection() {
  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <section className="section case-study" id="results">
      <div className="wrap case-study-grid">
        <header className="case-study-intro">
          <p className="kicker kicker--dark">Sample workflow</p>
          <h2>One after-hours call. One booked job.</h2>
          <p>
            A composite example of how Owlbell handles a typical plumbing emergency —
            not a named client testimonial. Your scripts, calendar, and routing rules
            are configured by our team during onboarding.
          </p>
          <dl className="case-study-stats">
            <div>
              <dt>Answer time</dt>
              <dd className="num">&lt;2s</dd>
            </div>
            <div>
              <dt>Owner notified</dt>
              <dd className="num">Instant SMS</dd>
            </div>
            <div>
              <dt>Job value</dt>
              <dd className="num">~$850</dd>
            </div>
          </dl>
        </header>

        <ol className="case-study-timeline">
          {TIMELINE.map((step, i) => (
            <li key={`${step.time}-${i}`}>
              <time className="num">{step.time}</time>
              <span>{step.event}</span>
            </li>
          ))}
        </ol>
      </div>

      <div className="wrap case-study-cta">
        <p>Want this running on your main line?</p>
        <button type="button" className="btn btn--copper" onClick={() => scrollTo("pricing")}>
          Start 7-day trial
        </button>
      </div>
    </section>
  );
}