"use client";

import { useState } from "react";
import { MOCK_SUBSCRIPTION, SubscriptionInfo } from "@/lib/dashboard-types";

const PLANS = [
  { id: 'basic', name: 'Launch', price: 1497, setup: 0, features: ['AI receptionist', '24/7 call answering', 'One number setup', 'Emergency routing', '30-day tuning'] },
  { id: 'pro', name: 'Growth', price: 4997, setup: 5000, features: ['Everything in Launch', 'Calendar booking', 'CRM handoff', 'After-hours routing', 'Revenue review', 'Priority support'] },
  { id: 'pro_plus', name: 'Scale', price: 9997, setup: 10000, features: ['Everything in Growth', 'Multiple locations', 'Custom reporting', 'Dedicated success lead', 'Volume pricing'] },
];

export default function DashboardBilling() {
  const [sub] = useState<SubscriptionInfo>(MOCK_SUBSCRIPTION);

  return (
    <div className="dash-page">
      <h1 className="dash-page-title">Billing</h1>
      <p className="dash-page-subtitle">Manage your subscription</p>

      <div className="dash-billing-card">
        <div className="dash-billing-plan">
          <div className="dash-billing-plan-name">{sub.plan} plan</div>
          <div className="dash-billing-plan-status">
            <span className={`dash-badge dash-badge--${sub.status === 'active' ? 'completed' : sub.status}`}>{sub.status}</span>
          </div>
        </div>
        <div className="dash-billing-amount">£{sub.amount.toLocaleString()}<span>/month</span></div>
        <div className="dash-billing-next">Next billing: {new Date(sub.nextBilling).toLocaleDateString()}</div>
      </div>

      <h2 className="dash-section-title" style={{ marginTop: 40 }}>Compare plans</h2>
      <div className="dash-plan-grid">
        {PLANS.map((plan) => (
          <div key={plan.id} className={`dash-plan-card${plan.name === sub.plan ? ' dash-plan-card--current' : ''}`}>
            <h3>{plan.name}</h3>
            <div className="dash-plan-price">£{plan.price.toLocaleString()}<span>/month</span></div>
            {plan.setup > 0 && <div className="dash-plan-setup">£{plan.setup.toLocaleString()} setup</div>}
            {plan.setup === 0 && <div className="dash-plan-setup">No setup fee</div>}
            <ul className="dash-plan-features">
              {plan.features.map((f, i) => <li key={i}>{f}</li>)}
            </ul>
            {plan.name === sub.plan ? (
              <div className="dash-plan-current-badge">Current plan</div>
            ) : (
              <button type="button" className="btn btn--outline" onClick={() => alert('Plan change requires Stripe portal integration')}>
                Switch to {plan.name}
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
