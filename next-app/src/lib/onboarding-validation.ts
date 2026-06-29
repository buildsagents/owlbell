export type OnboardingStepKey =
  | "business"
  | "calls"
  | "ai"
  | "knowledge"
  | "integrations"
  | "pricing"
  | "review";

export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

export function canAdvanceStep(
  stepKey: OnboardingStepKey,
  data: Record<string, string | boolean | string[]>,
): boolean {
  switch (stepKey) {
    case "business":
      return Boolean(
        String(data.businessName || "").trim() &&
          isValidEmail(String(data.email || "")) &&
          String(data.serviceArea || "").trim(),
      );
    case "calls":
      return Boolean(
        String(data.forwardNumber || "").trim() &&
          String(data.businessHours || "").trim() &&
          String(data.phoneSetup || "").trim(),
      );
    case "ai":
      return Boolean(String(data.personality || "").trim() && String(data.voiceId || "").trim());
    case "integrations":
      if (data.smsNotify === false) return true;
      return Boolean(String(data.smsNumber || "").trim());
    case "pricing":
      return Boolean(String(data.pricingTier || "").trim());
    default:
      return true;
  }
}

export function defaultGreetingForVertical(vertical: string, businessName: string): string {
  const name = businessName.trim() || "our team";
  const map: Record<string, string> = {
    plumbing: `Thanks for calling ${name} — how can we help with your plumbing today?`,
    hvac: `Thanks for calling ${name} — are you calling about heating, cooling, or maintenance?`,
    electrical: `Thanks for calling ${name} — tell me what's going on with your electrical issue.`,
    dental: `Thanks for calling ${name} — how can we help you today?`,
    legal: `Thank you for calling ${name} — what type of matter are you calling about?`,
  };
  return map[vertical] || map.plumbing;
}