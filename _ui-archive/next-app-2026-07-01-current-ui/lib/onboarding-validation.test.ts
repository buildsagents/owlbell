import { describe, expect, it } from "vitest";
import { isAuditIntakeValid, isValidEmail } from "./onboarding-validation";

const validDraft = {
  businessName: "Summit Plumbing",
  website: "summitplumbing.com",
  serviceArea: "Austin, TX",
  mainPhone: "(512) 555-0100",
  missedCallsPerWeek: "12",
  offersEmergencyPlumbing: "yes" as const,
  email: "owner@summit.com",
  leadSource: "hero",
};

describe("onboarding-validation", () => {
  it("validates email", () => {
    expect(isValidEmail("a@b.co")).toBe(true);
    expect(isValidEmail("bad")).toBe(false);
  });

  it("requires all audit intake fields", () => {
    expect(isAuditIntakeValid(validDraft)).toBe(true);
    expect(isAuditIntakeValid({ ...validDraft, businessName: "" })).toBe(false);
    expect(isAuditIntakeValid({ ...validDraft, offersEmergencyPlumbing: "" })).toBe(false);
    expect(isAuditIntakeValid({ ...validDraft, email: "not-an-email" })).toBe(false);
  });
});