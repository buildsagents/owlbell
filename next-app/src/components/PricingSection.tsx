"use client";

const CONTACT_EMAIL = "hello@owlbell.xyz";
const BOOKING_URL = process.env.NEXT_PUBLIC_BOOKING_URL;

const PLANS = [
  {
    id: "launch",
    name: "Launch",
    price: 1497,
    period: "/mo",
    subtitle: "For one-location operators who need the phones handled now",
    highlighted: false,
    cta: "Apply for Launch",
    features: [
      "AI receptionist configured for your business",
      "Call answering, lead capture, and instant owner alerts",
      "One phone number or call-forwarding setup",
      "Emergency routing rules",
      "Weekly script tuning for the first month",
    ],
  },
  {
    id: "growth",
    name: "Growth",
    price: 4997,
    period: "/mo",
    subtitle: "The core offer for serious service companies",
    highlighted: true,
    badge: "Core Offer",
    cta: "Book Growth Strategy Call",
    features: [
      "Everything in Launch",
      "Calendar booking and missed-call recovery workflow",
      "CRM or job-management handoff",
      "Advanced routing for after-hours and emergency calls",
      "Monthly revenue review and conversion tuning",
      "Priority support",
    ],
  },
  {
    id: "scale",
    name: "Scale",
    price: 9997,
    period: "+/mo",
    subtitle: "For multi-location or high-volume teams",
    highlighted: false,
    cta: "Talk to Sales",
    features: [
      "Everything in Growth",
      "Multiple locations, numbers, and routing trees",
      "Custom reporting and SLA options",
      "Dedicated success lead",
      "Quarterly workflow rebuilds",
    ],
  },
] as const;

function CheckIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden>
      <path
        fillRule="evenodd"
        d="M16.704 5.29a1 1 0 0 1 .006 1.414l-7.25 7.333a1 1 0 0 1-1.435-.02L3.29 10.71a1 1 0 0 1 1.42-1.408l3.185 3.235 6.54-6.617a1 1 0 0 1 1.414-.006Z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function openApplication(plan: string) {
  const subject = encodeURIComponent(`Owlbell ${plan} application`);
  const body = encodeURIComponent(
    [
      `I'm interested in Owlbell ${plan}.`,
      "",
      "Business name:",
      "Website:",
      "Service area:",
      "Average missed calls per week:",
      "Average job value:",
      "Current booking / CRM system:",
    ].join("\n")
  );

  if (BOOKING_URL) {
    window.open(BOOKING_URL, "_blank", "noopener,noreferrer");
    return;
  }

  window.location.href = `mailto:${CONTACT_EMAIL}?subject=${subject}&body=${body}`;
}

export default function PricingSection() {
  return (
    <section className="section section--last" id="pricing">
      <div className="wrap">
        <header className="section-header">
          <span className="section-eyebrow section-eyebrow--pill">Implementation</span>
          <h2>Pricing Built Around Recovered Revenue</h2>
          <p>
            This is not a cheap answering widget. Owlbell is a managed phone
            conversion system for companies where missed calls are already
            costing real money.
          </p>
        </header>

        <div className="pricing-grid">
          {PLANS.map((plan) => (
            <article
              key={plan.id}
              className={`pricing-card agency-card${plan.highlighted ? " pricing-card--featured" : ""}`}
            >
              {plan.highlighted && "badge" in plan && (
                <span className="pricing-popular">{plan.badge}</span>
              )}
              <h3 className="pricing-plan-name">{plan.name}</h3>
              <div className="pricing-price">
                <span className="pricing-amount">${plan.price.toLocaleString()}</span>
                <span className="pricing-period">{plan.period}</span>
              </div>
              <p className="pricing-subtitle">{plan.subtitle}</p>
              <ul className="pricing-features">
                {plan.features.map((feature) => (
                  <li key={feature}>
                    <span className="pricing-check">
                      <CheckIcon />
                    </span>
                    {feature}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className={`agency-btn ${plan.highlighted ? "agency-btn--primary" : "agency-btn--secondary"} agency-btn--block`}
                onClick={() => openApplication(plan.name)}
              >
                {plan.cta}
              </button>
            </article>
          ))}
        </div>

        <div className="pricing-founding" id="founding-offer">
          <div className="pricing-founding-copy">
            <strong>Founding Growth Sprint</strong>
            <span className="pricing-founding-headline">
              $1,000/mo credit for the first 3 months
            </span>
            <span className="pricing-founding-sub">
              For qualified Growth clients who allow a testimonial or anonymized case study
            </span>
          </div>
          <button
            type="button"
            className="agency-btn agency-btn--light"
            onClick={() => openApplication("Growth Founding Sprint")}
          >
            Apply for a Founding Slot
          </button>
        </div>
      </div>
    </section>
  );
}
