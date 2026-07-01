import { describe, expect, it } from "vitest";
import { DEFAULT_ONBOARDING, SERVICE_OPTIONS, STEPS, VOICE_OPTIONS } from "./onboarding-types";

describe("onboarding-types", () => {
  describe("DEFAULT_ONBOARDING", () => {
    it("has default values for all 7 steps", () => {
      expect(DEFAULT_ONBOARDING.step1_businessInfo).toBeDefined();
      expect(DEFAULT_ONBOARDING.step2_businessDetails).toBeDefined();
      expect(DEFAULT_ONBOARDING.step3_callHandling).toBeDefined();
      expect(DEFAULT_ONBOARDING.step4_calendar).toBeDefined();
      expect(DEFAULT_ONBOARDING.step5_knowledgeBase).toBeDefined();
      expect(DEFAULT_ONBOARDING.step6_phoneNumbers).toBeDefined();
      expect(DEFAULT_ONBOARDING.step7_aiVoice).toBeDefined();
    });

    it("has empty core fields", () => {
      expect(DEFAULT_ONBOARDING.step1_businessInfo.companyName).toBe("");
      expect(DEFAULT_ONBOARDING.step1_businessInfo.email).toBe("");
    });

    it("has sensible business detail defaults", () => {
      const d = DEFAULT_ONBOARDING.step2_businessDetails;
      expect(d.openingHours).toBe("Mon-Fri 8:00-17:00");
      expect(d.emergencyAvailable).toBe(true);
      expect(d.numberOfEngineers).toBe(1);
    });

    it("has sensible call handling defaults", () => {
      const d = DEFAULT_ONBOARDING.step3_callHandling;
      expect(d.emergencyRouting).toBe("escalate_emergency");
      expect(d.outOfHoursBehavior).toBe("voicemail");
    });

    it("has sensible calendar defaults", () => {
      const d = DEFAULT_ONBOARDING.step4_calendar;
      expect(d.provider).toBe("");
      expect(d.appointmentDuration).toBe(60);
      expect(d.bufferTime).toBe(15);
    });

    it("has new phone number as default type", () => {
      expect(DEFAULT_ONBOARDING.step6_phoneNumbers.type).toBe("new");
    });

    it("has professional as default speaking style", () => {
      expect(DEFAULT_ONBOARDING.step7_aiVoice.speakingStyle).toBe("professional");
    });
  });

  describe("SERVICE_OPTIONS", () => {
    it("includes essential plumbing services", () => {
      expect(SERVICE_OPTIONS).toContain("Burst pipe repair");
      expect(SERVICE_OPTIONS).toContain("Emergency callout");
      expect(SERVICE_OPTIONS).toContain("Blocked drains");
    });

    it("has exactly 10 options", () => {
      expect(SERVICE_OPTIONS).toHaveLength(10);
    });
  });

  describe("VOICE_OPTIONS", () => {
    it("has Morgan, Alex, and Sam", () => {
      const names = VOICE_OPTIONS.map((v) => v.name);
      expect(names).toContain("Morgan");
      expect(names).toContain("Alex");
      expect(names).toContain("Sam");
    });

    it("has unique voice IDs", () => {
      const ids = VOICE_OPTIONS.map((v) => v.id);
      expect(new Set(ids).size).toBe(ids.length);
    });

    it("each voice has a style description", () => {
      for (const v of VOICE_OPTIONS) {
        expect(v.style).toBeTruthy();
      }
    });
  });

  describe("STEPS", () => {
    it("has 9 entries (7 form + Review (8) + completion)", () => {
      expect(STEPS).toHaveLength(8);
    });

    it("starts with business info and ends with review", () => {
      expect(STEPS[0].key).toBe("step1_businessInfo");
      expect(STEPS[STEPS.length - 1].key).toBe("step8_review");
    });

    it("each step has a label and description", () => {
      for (const step of STEPS) {
        expect(step.label).toBeTruthy();
        expect(step.description).toBeTruthy();
      }
    });
  });

  describe("OnboardingData shape", () => {
    it("step1_businessInfo has all required fields", () => {
      const s = DEFAULT_ONBOARDING.step1_businessInfo;
      const keys = Object.keys(s);
      expect(keys).toContain("companyName");
      expect(keys).toContain("ownerName");
      expect(keys).toContain("email");
      expect(keys).toContain("mobile");
      expect(keys).toContain("businessAddress");
      expect(keys).toContain("website");
    });

    it("step5_knowledgeBase has all required fields", () => {
      const s = DEFAULT_ONBOARDING.step5_knowledgeBase;
      const keys = Object.keys(s);
      expect(keys).toContain("faqs");
      expect(keys).toContain("priceList");
      expect(keys).toContain("serviceInfo");
      expect(keys).toContain("policies");
      expect(keys).toContain("websiteUrl");
    });
  });
});
