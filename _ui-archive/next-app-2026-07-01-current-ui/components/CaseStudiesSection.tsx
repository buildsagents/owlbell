import Link from "next/link";
import { BEFORE_AFTER_METRICS, PROOF_TIMELINE } from "@/lib/proof-data";

export default function CaseStudiesSection() {
  return (
    <section className="section section--alt" id="case-studies">
      <div className="wrap">
        <div className="section-lead">
          <span className="section-label">Case study</span>
          <h2>Before Owlbell. After Owlbell.</h2>
          <p>Anonymized results from our pilot plumbing shop. Your numbers may vary, but the pattern is consistent.</p>
        </div>

        <div className="grid-4" style={{ marginBottom: "48px" }}>
          {BEFORE_AFTER_METRICS.map((stat) => (
            <div key={stat.id} className="card" style={{ textAlign: "center" }}>
              <div className="text-sm" style={{ color: "var(--gray-500)", marginBottom: "12px" }}>{stat.label}</div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "12px" }}>
                <span style={{ color: "var(--gray-400)", textDecoration: "line-through", fontSize: "1.125rem" }}>{stat.before}</span>
                <span style={{ color: "var(--gray-400)", fontSize: "0.875rem" }}>to</span>
                <span style={{ fontSize: "1.5rem", fontWeight: "700" }}>{stat.after}</span>
              </div>
              <div className="text-sm" style={{ color: "var(--blue)", marginTop: "8px", fontWeight: "600" }}>
                {stat.delta}
              </div>
            </div>
          ))}
        </div>

        <div className="case-study-grid">
          <div className="case-study-intro">
            <span className="section-label">Real timeline</span>
            <h3 style={{ fontSize: "1.25rem", fontWeight: "600" }}>Call to booked job in 2 minutes</h3>
            <p>
              A Friday-night burst pipe flows through the same pipeline we deploy on customer lines.
              From unanswered ring to booked dispatch slot in under 2 minutes.
            </p>
            <div className="case-stats">
              <div>
                <div className="case-stat-value num">1.8s</div>
                <span className="case-stat-label">Answer time</span>
              </div>
              <div>
                <div className="case-stat-value num">100%</div>
                <span className="case-stat-label">Answer rate</span>
              </div>
              <div>
                <div className="case-stat-value">&pound;850</div>
                <span className="case-stat-label">Job value</span>
              </div>
            </div>
          </div>

          <ol className="case-timeline">
            {PROOF_TIMELINE.map((step, i) => (
              <li key={`${step.time}-${i}`}>
                <time className="num">{step.time}</time>
                <span>{step.event}</span>
              </li>
            ))}
          </ol>
        </div>

        <div style={{ textAlign: "center", marginTop: "48px" }}>
          <Link href="/onboarding?source=case_studies" className="btn btn--primary">
            Get This for Your Shop
          </Link>
        </div>
      </div>
    </section>
  );
}
