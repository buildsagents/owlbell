import type { AuditIntakeDraft } from "@/lib/onboarding-storage";

export function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

export function isAuditIntakeValid(data: AuditIntakeDraft): boolean {
  return Boolean(
    data.businessName.trim() &&
      data.serviceArea.trim() &&
      data.mainPhone.trim() &&
      data.missedCallsPerWeek.trim() &&
      data.offersEmergencyPlumbing &&
      isValidEmail(data.email),
  );
}