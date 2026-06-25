'use client';

import { useState, useEffect } from 'react';
import { createClient } from '@/lib/supabase/client';
import { Subscription, PLAN_DETAILS, PlanTier } from '@/types';

const API_V1 = `${(process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '')}/api/v1`;

export default function BillingPage() {
  const [sub, setSub] = useState<Subscription | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [upgrading, setUpgrading] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();

    async function load() {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session?.access_token) throw new Error('Not authenticated');

        const res = await fetch(`${API_V1}/client-portal/overview`, {
          headers: { Authorization: `Bearer ${session.access_token}` },
        });

        if (res.ok) {
          const data = await res.json() as { subscription?: Subscription };
          if (data.subscription) setSub(data.subscription);
        } else {
          console.error('Failed to fetch subscription:', res.status);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load billing info');
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const handleUpgrade = async (plan: Exclude<PlanTier, 'enterprise'>) => {
    setUpgrading(plan);
    try {
      const res = await fetch('/api/stripe/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan }),
      });
      const { url } = await res.json();
      if (url) window.location.href = url;
    } finally {
      setUpgrading(null);
    }
  };

  const handlePortal = async () => {
    if (!sub?.stripe_customer_id) return;
    const res = await fetch('/api/stripe/portal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ customerId: sub.stripe_customer_id }),
    });
    const { url } = await res.json();
    if (url) window.location.href = url;
  };

  const plans = (['basic', 'pro', 'pro_plus'] as const).map(tier => ({
    tier,
    ...PLAN_DETAILS[tier],
  }));

  if (error) {
    return (
      <div style={{
        color: '#f87171', padding: '40px', textAlign: 'center',
        background: 'var(--panel)', borderRadius: '16px',
        border: '1px solid rgba(239,68,68,0.3)',
      }}>
        <div style={{ fontSize: '18px', fontWeight: 700, marginBottom: '8px' }}>Failed to load billing info</div>
        <div style={{ fontSize: '14px', opacity: 0.8 }}>{error}</div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ margin: 0, fontSize: '26px', fontWeight: 800, letterSpacing: '-0.02em' }}>
          Billing
        </h1>
        <p style={{ margin: '4px 0 0', color: 'var(--muted)', fontSize: '14px' }}>
          Manage your subscription and payment details.
        </p>
      </div>

      {/* Current plan */}
      {loading ? (
        <div style={{
          background: 'var(--panel)', border: '1px solid var(--line)',
          borderRadius: '16px', padding: '22px 24px', marginBottom: '28px',
          color: 'var(--muted)', fontSize: '14px',
        }}>
          Loading subscription…
        </div>
      ) : sub && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(245,158,11,0.10), rgba(56,189,248,0.07))',
          border: '1px solid rgba(245,158,11,0.35)',
          borderRadius: '16px',
          padding: '22px 24px',
          marginBottom: '28px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
          flexWrap: 'wrap',
        }}>
          <div>
            <div style={{ fontWeight: 800, fontSize: '20px', color: 'var(--brand2)', textTransform: 'capitalize' }}>
              {sub.plan_tier} Plan
            </div>
            <div style={{ fontSize: '13px', color: 'var(--muted)', marginTop: '4px' }}>
              Status: <strong style={{ color: sub.status === 'active' ? 'var(--good)' : '#f87171' }}>{sub.status}</strong>
              {sub.current_period_end &&
                ` · Next renewal: ${new Date(sub.current_period_end).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}`
              }
            </div>
          </div>
          <button
            className="btn btn-ghost"
            onClick={handlePortal}
            style={{ fontSize: '14px' }}
          >
            Manage / Cancel
          </button>
        </div>
      )}

      {/* Plan cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px' }}>
        {plans.map(({ tier, name, price, callLimit, features }) => {
          const isCurrent = sub?.plan_tier === tier;
          const isPopular = tier === 'pro';

          return (
            <div
              key={tier}
              style={{
                background: 'var(--panel)',
                border: `1px solid ${isPopular ? 'var(--brand)' : 'var(--line)'}`,
                borderRadius: '16px',
                padding: '24px',
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
                boxShadow: isPopular ? '0 0 0 1px var(--brand), 0 12px 32px rgba(245,158,11,0.15)' : 'none',
              }}
            >
              {isPopular && (
                <div style={{
                  position: 'absolute', top: '-11px', left: '50%', transform: 'translateX(-50%)',
                  background: 'var(--brand)', color: '#1a1206', fontWeight: 700,
                  fontSize: '11px', padding: '3px 12px', borderRadius: '999px',
                }}>
                  Most popular
                </div>
              )}
              <div style={{ fontSize: '36px', fontWeight: 800, letterSpacing: '-0.02em' }}>
                ${price}<span style={{ fontSize: '16px', fontWeight: 400, color: 'var(--muted)' }}>/mo</span>
              </div>
              <div style={{ fontWeight: 700, fontSize: '18px', margin: '4px 0 16px' }}>{name}</div>
              <ul style={{ listStyle: 'none', padding: 0, margin: '0 0 20px', flex: 1 }}>
                {features.map(f => (
                  <li key={f} style={{
                    padding: '7px 0', borderBottom: '1px solid var(--line)',
                    fontSize: '14px', color: 'var(--ink)',
                  }}>
                    <span style={{ color: 'var(--good)', fontWeight: 800, marginRight: '6px' }}>✓</span>
                    {f}
                  </li>
                ))}
              </ul>
              {isCurrent ? (
                <div style={{
                  textAlign: 'center', padding: '12px', borderRadius: '10px',
                  background: 'rgba(52,211,153,0.08)', color: 'var(--good)',
                  fontWeight: 700, fontSize: '14px', border: '1px solid rgba(52,211,153,0.25)',
                }}>
                  ✓ Current plan
                </div>
              ) : (
                <button
                  className={`btn ${isPopular ? 'btn-primary' : 'btn-ghost'}`}
                  onClick={() => handleUpgrade(tier)}
                  disabled={upgrading === tier}
                  style={{ opacity: upgrading === tier ? 0.6 : 1 }}
                >
                  {upgrading === tier ? 'Redirecting…' : `Upgrade to ${name}`}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <p style={{ marginTop: '18px', color: 'var(--muted)', fontSize: '13px', textAlign: 'center' }}>
        Enterprise (multi-location, white-label) — <a href="mailto:buildsagents@gmail.com" style={{ color: 'var(--accent)' }}>contact us</a> for custom pricing.
      </p>
    </div>
  );
}
