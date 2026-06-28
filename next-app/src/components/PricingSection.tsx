"use client";

import { useState } from "react";
import { FASTAPI_V1 } from "@/lib/consolidation";
import {
  formatSetupFee,
  friendlyCheckoutError,
  getCheckoutDisplay,
  type CheckoutPlanId,
} from "@/lib/checkout-display";

const ONBOARDING = [
  { day: "Day 0", text: "Subscribe + intake form" },
  { day: "Day 1", text: "Scripts, calendar, routing built by your specialist" },
  { day: "Day 2", text: "Test calls + go live on your line" },
];

const PRIMARY_PLANS = [
  {
    id: "basic" as const,
    name: "Launch",
    price: 1497,
    setupFee: null as number | null,
    blurb: "Every call answered. Owner alerts. Agency handles the wiring.",
    features: [
      "24/7 answering + lead capture",
      "Emergency routing rules",
      "One number or call forwarding",
      "30-day script tuning",
    ],
  },
  {
    id: "pro" as const,
    name: "Growth",
    price: 4997,
    setupFee: 5000,
    blurb: "Booking workflow, CRM handoff, and a dedicated success contact.",
    featured: true,
    features: [
      "Everything in Launch",
      "Calendar booking + missed-call recovery",
      "CRM / job-management handoff",
      "Monthly revenue review",
    ],
  },
];

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
      if (!url) throw new Error("No checkout URL returned. Please contact support.");
      window.location.href = url;
    } catch (err) {
      const raw = err instanceof Error ? err.message : "Something went wrong";
      setError(friendlyCheckoutError(raw));
      setLoading(false);
    }
  }

  return (
    <>
      <section className="section pricing-editorial" id="pricing">
        <div className="wrap">
          <header className="section-lead">
            <p className="kicker kicker--dark">Plans</p>
            <h2>Agency pricing for shops that can&apos;t miss calls</h2>
            <p>7-day trial on every plan. White-glove onboarding included. Cancel during trial.</p>
          </header>

          <div className="pricing-editorial-grid">
            {PRIMARY_PLANS.map((plan) => (
              <article
                key={plan.id}
                className={`pricing-ticket${"featured" in plan && plan.featured ? " pricing-ticket--featured" : ""}`}
              >
                {"featured" in plan && plan.featured && (
                  <span className="pricing-ticket-tag">Recommended</span>
                )}
                <h3>{plan.name}</h3>
                <p className="pricing-ticket-blurb">{plan.blurb}</p>
                <div className="pricing-ticket-price">
                  <span className="num">${plan.price.toLocaleString()}</span>
                  <span>/mo</span>
                </div>
                {plan.setupFee !== null && (
                  <p className="pricing-ticket-setup">+ {formatSetupFee(plan.setupFee)}</p>
                )}
                <ul>
                  {plan.features.map((f) => (
                    <li key={f}>{f}</li>
                  ))}
                </ul>
                <button
                  type="button"
                  className={`btn ${"featured" in plan && plan.featured ? "btn--copper" : "btn--outline"} btn--block`}
                  onClick={() => openCheckout(plan.id)}
                >
                  Start 7-day trial
                </button>
              </article>
            ))}
          </div>

          <article className="pricing-scale">
            <div>
              <h3>Scale</h3>
              <p>Multi-location, custom SLAs, dedicated success lead.</p>
            </div>
            <div className="pricing-scale-price">
              <span className="num">$9,997+</span>
              <span>/mo + {formatSetupFee(10000)}</span>
            </div>
            <button
              type="button"
              className="btn btn--outline"
              onClick={() => openCheckout("pro_plus")}
            >
              Start 7-day trial
            </button>
          </article>

          <ol className="pricing-onboard">
            {ONBOARDING.map((step) => (
              <li key={step.day}>
                <span className="num">{step.day}</span>
                <span>{step.text}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {modalPlan && checkout && (
        <div className="pricing-modal-overlay" role="presentation" onClick={closeModal}>
          <div
            className="pricing-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="pricing-modal-title"
            onClick={(e) => e.stopPropagation()}
          >
            <button type="button" className="pricing-modal-close" onClick={closeModal} aria-label="Close">
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
                className="btn btn--copper btn--block"
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