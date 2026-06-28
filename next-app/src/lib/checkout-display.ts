export type CheckoutPlanId = "basic" | "pro" | "pro_plus";

export const CHECKOUT_RATES: Record<
  CheckoutPlanId,
  { label: string; standard: number; founding: number }
> = {
  basic: { label: "Launch", standard: 1497, founding: 997 },
  pro: { label: "Growth", standard: 4997, founding: 3997 },
  pro_plus: { label: "Scale", standard: 9997, founding: 7997 },
};

export const FOUNDING_PROMO_CODE = "FOUNDING50";

export function normalizePlanId(plan: string): CheckoutPlanId {
  if (plan === "basic" || plan === "pro" || plan === "pro_plus") return plan;
  return "pro";
}

export function getCheckoutDisplay(plan: string, founding = false) {
  const id = normalizePlanId(plan);
  const rates = CHECKOUT_RATES[id];
  const monthly = founding ? rates.founding : rates.standard;
  return {
    planId: id,
    planLabel: rates.label,
    monthly,
    founding,
    buttonText: founding
      ? `Subscribe — ${rates.label} founding $${monthly}/mo`
      : `Subscribe — $${monthly}/mo`,
    foundingNote: founding
      ? `Founding plumber rate (50% off first 3 months). Promo ${FOUNDING_PROMO_CODE} applied at Stripe checkout when available.`
      : null,
  };
}

export const FOUNDING_SLOTS = { total: 20, remaining: 12 } as const;

export function foundingSlotsFillPercent(): number {
  return (FOUNDING_SLOTS.remaining / FOUNDING_SLOTS.total) * 100;
}

export function formatMonthlyPrice(amount: number): string {
  return `$${amount}/mo`;
}

export function foundingThreeMonthSavings(plan: CheckoutPlanId): number {
  const rates = CHECKOUT_RATES[plan];
  return 3 * (rates.standard - rates.founding);
}
