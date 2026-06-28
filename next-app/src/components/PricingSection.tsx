"use client";

import { useState } from "react";
import { FASTAPI_V1 } from "@/lib/consolidation";
import {
  formatSetupFee,
  friendlyCheckoutError,
  getCheckoutDisplay,
  type CheckoutPlanId,
} from "@/lib/checkout-display";

type PlanCard = {
  id: CheckoutPlanId;
  name: string;
  price: number;
  priceSuffix: string;
  setupFee: number | null;
  subtitle: string;
  highlighted: boolean;
  badge?: string;
  cta: string;
  features: string[];
};

const PLANS: PlanCard[] = [
  {
    id: "basic",
    name: "Launch",
    price: 1497,
    priceSuffix: "/mo",
    setupFee: null,
    subtitle: "Your managed reception agency — every call answered, zero hiring.",
    highlighted: false,
    cta: "Start 7-Day Trial",
    features: [
      "Agency-configured receptionist trained on your business and service area",
      "24/7 call answering, lead capture, and instant owner alerts",
      "One number or call-forwarding setup — we handle the wiring",
      "Emergency routing rules for after-hours and urgent jobs",
      "Script tuning during your first 30 days",
    ],
  },
  {
    id: "pro",
    name: "Growth",
    price: 4997,
    priceSuffix: "/mo",
    setupFee: 5000,
    subtitle: "The flagship managed system for companies serious about recovered revenue.",
    highlighted: true,
    badge: "Most Popular",
    cta: "Start 7-Day Trial",
    features: [
      "Everything in Launch",
      "Calendar booking and missed-call recovery workflow",
      "CRM or job-management handoff",
      "Advanced routing for after-hours and emergency calls",
      "Monthly revenue review and conversion tuning",
      "Priority support with a dedicated success contact",
    ],
  },
  {
    id: "pro_plus",
    name: "Scale",
    price: 9997,
    priceSuffix: "+/mo",
    setupFee: 10000,
    subtitle: "For multi-location teams and high-volume operators who need white-glove rollout.",
    highlighted: false,
    cta: "Start 7-Day Trial",
    features: [
      "Everything in Growth",
      "Multiple locations, numbers, and routing trees",
      "Custom reporting, SLAs, and escalation paths",
      "Dedicated success lead and quarterly workflow rebuilds",
      "Volume pricing available for enterprise rollouts",
    ],
  },
];

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

export default function PricingSection() {
  const [modalPlan, setModalPlan] = useState<CheckoutPlanId | null>(null);
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const checkout = modalPlan ? getCheckoutDisplay(modalPlan) : null;

  function openCheckout(planId: CheckoutPlanId) {
    setModalPlan(planId);
    setEmail("");
    setError(null);
  }

  function closeModal() {
    if (loading) return;
    setModalPlan(null);
    setError(null);
  }

  async function handleCheckout(e: React.FormEvent) {
    e.preventDefault();
    if (!modalPlan || !email.trim()) return;

    setLoading(true);
    setError(null);

    const display = getCheckoutDisplay(modalPlan);

    try {
      const res = await fetch(`${FASTAPI_V1}/billing/public-checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          plan: modalPlan,
          period: "monthly",
          email: email.trim(),
          include_setup_fee: display.includeSetupFee,
        }),
      });

      const json = await res.json();

      if (!res.ok) {
        const detail =
          typeof json?.detail === "string"
            ? json.detail
            : json?.message || "Checkout unavailable";
        throw new Error(friendlyCheckoutError(detail));
      }

      const url = json?.data?.url;
      if (!url) {
        throw new Error("No checkout URL returned. Please contact support.");
      }

      window.location.href = url;
    } catch (err) {
      const raw = err instanceof Error ? err.message : "Something went wrong";
      setError(friendlyCheckoutError(raw));
      setLoading(false);
    }
  }

  return (
    <>
      <section className="section section--last" id="pricing">
        <div className="wrap">
          <header className="section-header">
            <span className="section-eyebrow section-eyebrow--pill">Pricing</span>
            <h2>Agency Pricing — Built for Companies That Can&apos;t Afford Missed Calls</h2>
            <p>
              Owlbell is a premium AI receptionist agency — not software you
              configure yourself. Every plan includes human-led setup, script
              tuning, and ongoing optimization from a dedicated success team.
            </p>
          </header>

          <div className="pricing-grid">
            {PLANS.map((plan) => (
              <article
                key={plan.id}
                className={`pricing-card agency-card${plan.highlighted ? " pricing-card--featured" : ""}`}
              >
                {plan.highlighted && plan.badge && (
                  <span className="pricing-popular">{plan.badge}</span>
                )}
                <h3 className="pricing-plan-name">{plan.name}</h3>
                <div className="pricing-price">
                  <span className="pricing-amount">
                    ${plan.price.toLocaleString()}
                  </span>
                  <span className="pricing-period">{plan.priceSuffix}</span>
                </div>
                {plan.setupFee !== null && (
                  <p className="pricing-setup-fee">
                    + {formatSetupFee(plan.setupFee)}
                  </p>
                )}
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
                  onClick={() => openCheckout(plan.id)}
                >
                  {plan.cta}
                </button>
              </article>
            ))}
          </div>

          <p className="pricing-footnote">
            All plans include a 7-day trial with white-glove onboarding. Subscribe
            online instantly — no sales call required. Cancel anytime during trial.
          </p>
        </div>
      </section>

      {modalPlan && checkout && (
        <div
          className="pricing-modal-overlay"
          role="presentation"
          onClick={closeModal}
        >
          <div
            className="pricing-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="pricing-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="pricing-modal-close"
              onClick={closeModal}
              aria-label="Close"
            >
              ✕
            </button>
            <h3 id="pricing-modal-title">{checkout.modalTitle}</h3>
            <p>{checkout.modalNote}</p>
            <form onSubmit={handleCheckout}>
              <label htmlFor="checkout-email" className="sr-only">
                Email address
              </label>
              <input
                id="checkout-email"
                type="email"
                placeholder="you@yourcompany.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
                disabled={loading}
              />
              {error && <p className="pricing-modal-error">{error}</p>}
              <button
                type="submit"
                className="agency-btn agency-btn--primary agency-btn--block"
                disabled={loading || !email.trim()}
              >
                {loading ? "Redirecting to Stripe…" : checkout.buttonText}
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}