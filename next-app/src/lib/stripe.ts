import Stripe from 'stripe';
import { PlanTier } from '@/types';

if (!process.env.STRIPE_SECRET_KEY) {
  console.warn('[stripe] STRIPE_SECRET_KEY not set - billing features disabled.');
}

export const stripe = process.env.STRIPE_SECRET_KEY
  ? new Stripe(process.env.STRIPE_SECRET_KEY, {
      apiVersion: '2026-06-24.dahlia',
      typescript: true,
    })
  : null;

// ---------------------------------------------------------------------------
// Plan -> Stripe Price ID mapping
// Set these in .env.local after creating products in your Stripe dashboard.
// ---------------------------------------------------------------------------
export const STRIPE_PRICE_IDS: Record<PlanTier, string | undefined> = {
  basic:    process.env.STRIPE_PRICE_BASIC,
  pro:      process.env.STRIPE_PRICE_PRO,
  pro_plus: process.env.STRIPE_PRICE_PRO_PLUS,
};

// ---------------------------------------------------------------------------
// Create a Stripe Checkout session for a given plan and org
// ---------------------------------------------------------------------------
export async function createCheckoutSession({
  plan,
  orgId,
  customerEmail,
  successUrl,
  cancelUrl,
}: {
  plan: PlanTier;
  orgId: string;
  customerEmail?: string;
  successUrl: string;
  cancelUrl: string;
}): Promise<string | null> {
  if (!stripe) return null;

  const priceId = STRIPE_PRICE_IDS[plan];
  if (!priceId) {
    console.error(`[stripe] No price ID configured for plan: ${plan}`);
    return null;
  }

  const session = await stripe.checkout.sessions.create({
    mode: 'subscription',
    payment_method_types: ['card'],
    line_items: [{ price: priceId, quantity: 1 }],
    customer_email: customerEmail,
    success_url: successUrl,
    cancel_url: cancelUrl,
    metadata: { org_id: orgId, plan_tier: plan },
    subscription_data: {
      trial_period_days: 7,
      metadata: { org_id: orgId, plan_tier: plan },
    },
  });

  return session.url;
}

// ---------------------------------------------------------------------------
// Create a Stripe Customer Portal session for subscription management
// ---------------------------------------------------------------------------
export async function createPortalSession({
  customerId,
  returnUrl,
}: {
  customerId: string;
  returnUrl: string;
}): Promise<string | null> {
  if (!stripe) return null;

  const session = await stripe.billingPortal.sessions.create({
    customer: customerId,
    return_url: returnUrl,
  });

  return session.url;
}
