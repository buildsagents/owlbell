import { describe, expect, it } from "vitest";
import { canAdvanceStep, defaultGreetingForVertical, isValidEmail } from "./onboarding-validation";

describe("onboarding-validation", () => {
  it("validates email", () => {
    expect(isValidEmail("a@b.co")).toBe(true);
    expect(isValidEmail("bad")).toBe(false);
  });

  it("gates business step", () => {
    expect(
      canAdvanceStep("business", { businessName: "Acme", email: "a@b.co", serviceArea: "Austin" }),
    ).toBe(true);
    expect(canAdvanceStep("business", { businessName: "", email: "a@b.co", serviceArea: "Austin" })).toBe(false);
  });

  it("generates vertical greetings", () => {
    expect(defaultGreetingForVertical("hvac", "Summit HVAC")).toContain("heating");
  });
});