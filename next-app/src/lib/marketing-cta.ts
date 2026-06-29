export const CTA_START_TRIAL = "Start Free Trial";
export const CTA_LAUNCH_AI = "Launch Your AI Receptionist";
export const ONBOARDING_PATH = "/onboarding";
export const DEMO_PATH = "/demo";

export function onboardingHref(extra?: Record<string, string>): string {
  if (!extra || Object.keys(extra).length === 0) return ONBOARDING_PATH;
  const params = new URLSearchParams(extra);
  return `${ONBOARDING_PATH}?${params.toString()}`;
}