"use client";

const STATS = [
  { id: "recovered", value: "$14,850", label: "Avg. monthly revenue recovered", delta: "+18.6%" },
  { id: "calls", value: "247", label: "Calls answered per week", delta: "+12.4%" },
  { id: "booked", value: "38", label: "Jobs booked per month", delta: "+26.7%" },
  { id: "prevented", value: "52", label: "Missed calls prevented", delta: "+8.3%" },
];

const OUTCOMES = [
  {
    id: "summit",
    company: "Summit Plumbing Co.",
    location: "Denver, CO",
    metric: "$19,200/mo recovered",
    quote:
      "We were losing after-hours emergency calls every weekend. Within 30 days, Owlbell was booking burst-pipe jobs we used to miss entirely.",
  },
  {
    id: "ridge",
    company: "RidgeLine Plumbing",
    location: "Phoenix, AZ",
    metric: "38 jobs booked in month one",
    quote:
      "Our receptionist quit and we couldn't hire fast enough. The agency picked up every call, routed emergencies, and kept our calendar full.",
  },
  {
    id: "coastal",
    company: "Coastal Pipe & Drain",
    location: "Charleston, SC",
    metric: "<2s average answer time",
    quote:
      "Callers can't tell it's not our front desk. Scripts sound like us, bookings land in ServiceTitan, and I get a text before I even check voicemail.",
  },
];

export default function ProofResultsSection() {
  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <section className="section proof-section" id="results">
      <div className="wrap">
        <header className="section-header">
          <span className="section-eyebrow section-eyebrow--pill">Proven results</span>
          <h2>Revenue Recovery — Not Vanity Metrics</h2>
          <p>
            Owlbell clients track recovered revenue, booked jobs, and missed-call
            prevention in one dashboard. These are the outcomes our agency
            optimizes every week.
          </p>
          <p className="proof-disclaimer">
            Illustrative examples based on typical plumbing agency results — not
            verified client testimonials. Your results depend on call volume,
            service area, and job mix.
          </p>
        </header>

        <div className="proof-stats">
          {STATS.map((stat) => (
            <article key={stat.id} className="proof-stat agency-card">
              <span className="proof-stat-value">{stat.value}</span>
              <span className="proof-stat-label">{stat.label}</span>
              <span className="proof-stat-delta">
                <span aria-hidden>↑</span> {stat.delta} vs prior period
              </span>
              <span className="proof-stat-note">Illustrative</span>
            </article>
          ))}
        </div>

        <div className="proof-outcomes">
          {OUTCOMES.map((outcome) => (
            <article key={outcome.id} className="proof-outcome agency-card">
              <div className="proof-outcome-head">
                <div>
                  <h3>{outcome.company}</h3>
                  <span className="proof-outcome-location">{outcome.location}</span>
                </div>
                <span className="proof-outcome-metric">{outcome.metric}</span>
              </div>
              <blockquote>
                <p>&ldquo;{outcome.quote}&rdquo;</p>
              </blockquote>
            </article>
          ))}
        </div>

        <div className="proof-cta">
          <p>Ready to see these numbers on your dashboard?</p>
          <button
            type="button"
            className="agency-btn agency-btn--primary"
            onClick={() => scrollTo("pricing")}
          >
            Start 7-Day Trial
            <span aria-hidden>→</span>
          </button>
        </div>
      </div>
    </section>
  );
}