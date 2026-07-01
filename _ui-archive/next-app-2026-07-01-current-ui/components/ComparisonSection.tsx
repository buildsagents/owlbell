import Link from "next/link";

const COMPARE_DATA = [
  {
    name: "Voicemail",
    features: [
      { text: "Answered after hours", ok: false },
      { text: "Emergency qualification", ok: false },
      { text: "Job booking", ok: false },
      { text: "Owner notification", ok: false },
      { text: "Call recording", ok: false },
    ],
    featured: false,
  },
  {
    name: "Owlbell",
    features: [
      { text: "Answered after hours", ok: true },
      { text: "Emergency qualification", ok: true },
      { text: "Job booking", ok: true },
      { text: "Owner notification", ok: true },
      { text: "Call recording", ok: true },
    ],
    featured: true,
  },
  {
    name: "Human answering service",
    features: [
      { text: "Answered after hours", ok: true },
      { text: "Emergency qualification", ok: false },
      { text: "Job booking", ok: false },
      { text: "Owner notification", ok: false },
      { text: "Call recording", ok: false },
    ],
    featured: false,
  },
];

export default function ComparisonSection() {
  return (
    <section className="section" id="compare">
      <div className="wrap">
        <div className="section-lead">
          <span className="section-label">Compare</span>
          <h2>Voicemail takes messages. We book jobs.</h2>
          <p>See how Owlbell compares to the alternatives your callers face.</p>
        </div>
        <div className="compare-grid">
          {COMPARE_DATA.map((col) => (
            <div key={col.name} className={`compare-card${col.featured ? " compare-card--featured" : ""}`}>
              <h3 style={{ color: col.featured ? "var(--blue)" : undefined }}>{col.name}</h3>
              <ul className="compare-list">
                {col.features.map((f) => (
                  <li key={f.text} className={f.ok ? "is-checked" : "is-cross"}>
                    {f.text}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div style={{ textAlign: "center", marginTop: "32px" }}>
          <Link href="/onboarding?source=compare" className="btn btn--primary">
            Book a Demo
          </Link>
        </div>
      </div>
    </section>
  );
}
