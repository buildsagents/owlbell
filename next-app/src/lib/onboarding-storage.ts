export const ONBOARDING_STORAGE_KEY = "owlbell_onboarding_v2";

export type OnboardingDraft = {
  draftId?: string;
  step: number;
  updatedAt: string;
  businessName: string;
  email: string;
  serviceArea: string;
  website: string;
  vertical: string;
  callsPerWeek: string;
  avgTicket: string;
  afterHoursPct: string;
  voiceId: string;
  personality: string;
  businessHours: string;
  emergencyRouting: string;
  kbNotes: string;
  kbFileNames: string[];
  calendarProvider: string;
  crmProvider: string;
  phoneSetup: string;
  forwardNumber: string;
  smsNumber: string;
  smsNotify: boolean;
  pricingTier: string;
  roiMonthlyLoss?: number;
  roiAnnualRecovery?: number;
};

export const defaultDraft = (): OnboardingDraft => ({
  step: 0,
  updatedAt: new Date().toISOString(),
  businessName: "",
  email: "",
  serviceArea: "",
  website: "",
  vertical: "plumbing",
  callsPerWeek: "40",
  avgTicket: "350",
  afterHoursPct: "35",
  voiceId: "warm_professional",
  personality: "friendly_expert",
  businessHours: "Mon-Fri 8am-6pm",
  emergencyRouting: "escalate_emergency",
  kbNotes: "",
  kbFileNames: [],
  calendarProvider: "google",
  crmProvider: "none",
  phoneSetup: "forward_existing",
  forwardNumber: "",
  smsNumber: "",
  smsNotify: true,
  pricingTier: "growth",
});

export function loadDraft(): OnboardingDraft {
  if (typeof window === "undefined") return defaultDraft();
  try {
    const raw = localStorage.getItem(ONBOARDING_STORAGE_KEY);
    if (!raw) return defaultDraft();
    return { ...defaultDraft(), ...JSON.parse(raw) };
  } catch {
    return defaultDraft();
  }
}

export function saveDraft(draft: OnboardingDraft): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(
    ONBOARDING_STORAGE_KEY,
    JSON.stringify({ ...draft, updatedAt: new Date().toISOString() }),
  );
}

export function clearDraft(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ONBOARDING_STORAGE_KEY);
}