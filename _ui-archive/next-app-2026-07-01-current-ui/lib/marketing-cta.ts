export const CTA_PRIMARY = "Get Free Missed-Call Audit";
export const CTA_SECONDARY = "Hear Sample Call";
export const CTA_DEMO_FLOW = "Get this flow for your plumbing company";

export const ONBOARDING_PATH = "/onboarding";
export const DEMO_PATH = "/demo";
export const SAMPLE_CALL_SECTION_ID = "sample-call";

/** Client acquisition offer ladder - audit -> trial -> paid */
export const OFFER_LADDER = [
  {
    id: "audit",
    label: "Free missed-call audit",
    detail: "2-min intake -> recovery report + sample script. No billing upfront.",
    href: ONBOARDING_PATH,
  },
  {
    id: "trial",
    label: "7-day call capture test",
    detail: "Forward overflow after audit. Prove booked jobs before full Launch.",
    href: ONBOARDING_PATH,
  },
  {
    id: "launch",
    label: "Launch - £1,197/mo",
    detail: "24/7 answering, emergency routing, owner SMS. Pays for itself at 3-5 jobs/mo.",
    href: ONBOARDING_PATH,
  },
  {
    id: "growth",
    label: "Growth - £3,997/mo",
    detail: "Calendar booking + Jobber / ServiceTitan / Housecall Pro handoff.",
    href: ONBOARDING_PATH,
  },
] as const;

export const MANAGED_SETUP_KICKER =
  "Managed setup. No tech work. Forward missed calls and we handle the rest.";

export const MANAGED_SETUP_STEPS = [
  {
    id: "setup",
    label: "We set it up for you",
    detail:
      "Tell us your services, hours, and emergency rules. Our team configures voice, scripts, and routing - no tech work on your end.",
  },
  {
    id: "forward",
    label: "You forward missed calls",
    detail:
      "Forward your main line or after-hours overflow to Owlbell. Your crew keeps doing jobs.",
  },
  {
    id: "tune",
    label: "We tune the script",
    detail:
      "We refine greetings, triage, and booking rules from real calls until it sounds like your shop.",
  },
  {
    id: "sms",
    label: "You get booked jobs by SMS",
    detail:
      "Owner text with caller, issue, time slot, and estimated job value - before they dial the next plumber.",
  },
] as const;

export function onboardingHref(extra?: Record<string, string>): string {
  if (!extra || Object.keys(extra).length === 0) return ONBOARDING_PATH;
  const params = new URLSearchParams(extra);
  return `${ONBOARDING_PATH}?${params.toString()}`;
}

/** Primary CTA - missed-call audit / onboarding intake */
export function auditHref(extra?: Record<string, string>): string {
  return onboardingHref({ source: "audit", ...extra });
}

/** Secondary CTA - inline sample on homepage, full demo page elsewhere */
export function sampleCallHref(onHomepage = false): string {
  return onHomepage ? `#${SAMPLE_CALL_SECTION_ID}` : DEMO_PATH;
}