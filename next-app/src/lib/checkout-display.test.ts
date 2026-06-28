import { describe, expect, it } from "vitest";
import {
  formatMonthlyPrice,
  formatSetupFee,
  friendlyCheckoutError,
  getCheckoutDisplay,
  getPlanConfig,
  normalizePlanId,
  PRICING_PLANS,
} from "./checkout-display";

describe("PRICING_PLANS", () => {
  it("defines Launch, Growth, and Scale tiers without a Basic tier", () => {
    expect(PRICING_PLANS.map((p) => p.name)).toEqual(["Launch", "Growth", "Scale"]);
    expect(PRICING_PLANS.some((p) => p.monthly === 797)).toBe(false);
  });

  it("aligns setup fees with backend MANAGED_PLANS", () => {
    expect(PRICING_PLANS.find((p) => p.id === "pro")?.setupFee).toBe(5000);
    expect(PRICING_PLANS.find((p) => p.id === "pro_plus")?.setupFee).toBe(10000);
  });
});

describe("getCheckoutDisplay", () => {
  it("returns Growth pricing with setup fee", () => {
    const d = getCheckoutDisplay("pro");
    expect(d.monthly).toBe(4997);
    expect(d.setupFee).toBe(5000);
    expect(d.includeSetupFee).toBe(true);
    expect(d.buttonText).toContain("7-Day Trial");
  });

  it("returns Launch pricing without setup fee", () => {
    const d = getCheckoutDisplay("basic");
    expect(d.monthly).toBe(1497);
    expect(d.setupFee).toBeNull();
    expect(d.includeSetupFee).toBe(false);
    expect(d.modalNote).toContain("White-glove agency onboarding included");
  });

  it("returns Scale pricing with trial CTA", () => {
    const d = getCheckoutDisplay("pro_plus");
    expect(d.monthly).toBe(9997);
    expect(d.setupFee).toBe(10000);
    expect(d.buttonText).toContain("7-Day Trial");
  });

  it("normalizes unknown plan to pro", () => {
    expect(normalizePlanId("unknown")).toBe("pro");
    expect(getPlanConfig("unknown").name).toBe("Growth");
  });
});

describe("formatMonthlyPrice", () => {
  it("formats Growth rate for UI", () => {
    expect(formatMonthlyPrice(getCheckoutDisplay("pro").monthly)).toBe("$4,997/mo");
  });

  it("formats Launch rate for UI", () => {
    expect(formatMonthlyPrice(getCheckoutDisplay("basic").monthly)).toBe("$1,497/mo");
  });
});

describe("formatSetupFee", () => {
  it("formats setup fee copy", () => {
    expect(formatSetupFee(5000)).toBe("$5,000 one-time setup");
  });
});

describe("friendlyCheckoutError", () => {
  it("maps billing-not-configured errors", () => {
    expect(friendlyCheckoutError("Stripe secret key not configured")).toContain(
      "hello@owlbell.xyz"
    );
  });

  it("passes through unknown errors with support contact", () => {
    expect(friendlyCheckoutError("random failure")).toContain("hello@owlbell.xyz");
  });
});