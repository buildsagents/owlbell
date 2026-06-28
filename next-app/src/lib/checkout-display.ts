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
  { id: "pro", name: "Growth", monthly: 4997, setupFee: 5000 },
  { id: "pro_plus", name: "Scale", monthly: 9997, setupFee: 10000, customPricing: true },
];

const TRIAL_DAYS = 7;

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
    buttonText: `Start ${TRIAL_DAYS}-Day Trial — ${config.name}`,
    modalTitle: `Subscribe to ${config.name}`,
    modalNote:
      config.setupFee !== null
        ? `$${config.monthly.toLocaleString()}/mo after your trial. Includes white-glove agency onboarding ($${config.setupFee.toLocaleString()} one-time).`
        : `$${config.monthly.toLocaleString()}/mo after your trial. White-glove agency onboarding included.`,
  };
}

export function formatMonthlyPrice(amount: number): string {
  return `$${amount.toLocaleString()}/mo`;
}

export function formatSetupFee(amount: number): string {
  return `$${amount.toLocaleString()} one-time setup`;
}

export function friendlyCheckoutError(raw: string): string {
  const lower = raw.toLowerCase();
  if (lower.includes("not configured") || lower.includes("503")) {
    return "Checkout is temporarily unavailable. Email hello@owlbell.xyz and we'll get you started.";
  }
  if (lower.includes("unknown plan") || lower.includes("400")) {
    return "That plan isn't available right now. Try again or contact support.";
  }
  if (lower.includes("network") || lower.includes("fetch")) {
    return "Connection issue — check your internet and try again.";
  }
  return "Something went wrong starting checkout. Try again or email hello@owlbell.xyz.";
}