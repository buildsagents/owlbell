export const ONBOARDING_STORAGE_KEY = "owlbell_audit_intake_v1";

export type EmergencyPlumbingAnswer = "" | "yes" | "no";

export type AuditIntakeDraft = {
  businessName: string;
  website: string;
  serviceArea: string;
  mainPhone: string;
  missedCallsPerWeek: string;
  offersEmergencyPlumbing: EmergencyPlumbingAnswer;
  email: string;
  leadSource: string;
  roiRecoveredMonthly?: number;
};

/** @deprecated Use AuditIntakeDraft - kept for draft API compatibility */
export type OnboardingDraft = AuditIntakeDraft & {
  step?: number;
  draftId?: string;
  updatedAt?: string;
};

export const defaultAuditIntake = (): AuditIntakeDraft => ({
  businessName: "",
  website: "",
  serviceArea: "",
  mainPhone: "",
  missedCallsPerWeek: "",
  offersEmergencyPlumbing: "",
  email: "",
  leadSource: "",
});

export const defaultDraft = defaultAuditIntake;

export function loadDraft(): AuditIntakeDraft {
  if (typeof window === "undefined") return defaultAuditIntake();
  try {
    const raw = localStorage.getItem(ONBOARDING_STORAGE_KEY);
    if (!raw) return defaultAuditIntake();
    return { ...defaultAuditIntake(), ...JSON.parse(raw) };
  } catch {
    return defaultAuditIntake();
  }
}

export function saveDraft(draft: AuditIntakeDraft): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ONBOARDING_STORAGE_KEY, JSON.stringify(draft));
}

export function clearDraft(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ONBOARDING_STORAGE_KEY);
}