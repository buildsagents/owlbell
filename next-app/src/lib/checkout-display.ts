export type CheckoutPlanId = "basic" | "pro" | "pro_plus";

export type PricingPlanConfig = {
  id: CheckoutPlanId;
  name: string;
  monthly: number;
  setupFee: number | null;
  customPricing?: boolean;
};

export const PRICING_PLANS: PricingPlanConfig[] = [
  { id: "basic", name: "Launch", monthly: 1497, setupFee: null },
  { id: "pro", name: "Growth", monthly: 4997, setupFee: 1997 },
  { id: "pro_plus", name: "Scale", monthly: 9997, setupFee: 1997, customPricing: true },
];

export function normalizePlanId(plan: string): CheckoutPlanId {
  if (plan === "basic" || plan === "pro" || plan === "pro_plus") return plan;
  return "pro";
}

export function getPlanConfig(plan: string): PricingPlanConfig {
  const id = normalizePlanId(plan);
  return PRICING_PLANS.find((p) => p.id === id) ?? PRICING_PLANS[1];
}

export function getCheckoutDisplay(plan: string) {
  const config = getPlanConfig(plan);
  return {
    planId: config.id,
    planLabel: config.name,
    monthly: config.monthly,
    setupFee: config.setupFee,
    includeSetupFee: config.setupFee !== null,
    buttonText: `Start 7-Day Trial — ${config.name}`,
    modalTitle: `Subscribe to ${config.name}`,
    modalNote:
      config.setupFee !== null
        ? `$${config.monthly.toLocaleString()}/mo after your trial. One-time setup fee of $${config.setupFee.toLocaleString()} due at checkout.`
        : `$${config.monthly.toLocaleString()}/mo after your trial. No setup fee on Launch.`,
  };
}

export function formatMonthlyPrice(amount: number): string {
  return `$${amount.toLocaleString()}/mo`;
}

export function formatSetupFee(amount: number): string {
  return `$${amount.toLocaleString()} one-time setup`;
}