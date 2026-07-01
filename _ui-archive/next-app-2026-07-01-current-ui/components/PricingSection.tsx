import Link from "next/link";
import { PRIMARY_PLAN_DISPLAY, SCALE_PLAN_DISPLAY, PRICING_QUALIFIERS } from "@/lib/pricing-display";

export default function PricingSection() {
  return (
    <section className="section section--alt" id="pricing">
      <div className="wrap">
        <div className="section-lead">
          <span className="section-label">Pricing</span>
          <h2>Clear, transparent. No surprises.</h2>
          <p>
            Recovered job value makes this easy. If we don&apos;t book more jobs than your monthly
            cost, you shouldn&apos;t stay.
          </p>
        </div>

        <div className="pricing-grid">
          {PRIMARY_PLAN_DISPLAY.map((plan) => (
            <article
              key={plan.id}
              className={`pricing-card${plan.featured ? " pricing-card--featured" : ""}`}
            >
              {plan.featured && <span className="pricing-badge">Recommended</span>}
              <div className="pricing-name">{plan.name}</div>
              <div className="pricing-subtitle">{plan.payoff}</div>
              <div className="pricing-amount">{plan.rate}</div>
              <div className="pricing-period">per month</div>
              {plan.setupFee && <div className="pricing-setup">{plan.setupFee}</div>}
              <div className="pricing-blurb" style={{ fontSize: "0.875rem", color: "var(--gray-500)", marginBottom: "20px" }}>
                {plan.blurb}
              </div>
              <ul className="pricing-features">
                {plan.features.map((f) => (
                  <li key={f}>{f}</li>
                ))}
              </ul>
              <Link
                href={`/onboarding?source=pricing&plan=${plan.id}`}
                className={`btn ${plan.featured ? "btn--primary" : "btn--secondary"} btn--block`}
              >
                Book a Demo
              </Link>
            </article>
          ))}

          <article className="pricing-card">
            <div className="pricing-name">Scale</div>
            <div className="pricing-subtitle">{SCALE_PLAN_DISPLAY.payoff}</div>
            <div className="pricing-amount">{SCALE_PLAN_DISPLAY.rate}</div>
            <div className="pricing-period">per month</div>
            {SCALE_PLAN_DISPLAY.setupFee && <div className="pricing-setup">{SCALE_PLAN_DISPLAY.setupFee}</div>}
            <div className="pricing-blurb" style={{ fontSize: "0.875rem", color: "var(--gray-500)", marginBottom: "20px" }}>
              {SCALE_PLAN_DISPLAY.blurb}
            </div>
            <ul className="pricing-features">
              <li>Everything in Growth</li>
              <li>Multi-location routing</li>
              <li>Custom SLAs</li>
              <li>Dedicated success lead</li>
            </ul>
            <Link
              href="/onboarding?source=pricing&plan=scale"
              className="btn btn--secondary btn--block"
            >
              Contact Sales
            </Link>
          </article>
        </div>

        <ul className="pricing-qualifiers" style={{
          listStyle: "none", display: "flex", flexWrap: "wrap", justifyContent: "center",
          gap: "8px 20px", margin: "0 0 24px", padding: 0, fontSize: "0.875rem", color: "var(--gray-500)"
        }}>
          {PRICING_QUALIFIERS.map((item) => (
            <li key={item} style={{ position: "relative", paddingLeft: "16px" }}>
              <span style={{ position: "absolute", left: 0, color: "var(--blue)" }}>&check;</span> {item}
            </li>
          ))}
        </ul>

        <p className="pricing-note">
          Every plan includes a 7-day trial. Cancel before day 7 and you are not charged.
          Month-to-month after trial. No long-term contract.
        </p>
      </div>
    </section>
  );
}
