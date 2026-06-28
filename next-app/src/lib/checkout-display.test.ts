import { describe, expect, it } from "vitest";
import {
  formatMonthlyPrice,
  formatSetupFee,
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
});

describe("getCheckoutDisplay", () => {
  it("returns Growth pricing with setup fee", () => {
    const d = getCheckoutDisplay("pro");
    expect(d.monthly).toBe(4997);
    expect(d.setupFee).toBe(1997);
    expect(d.includeSetupFee).toBe(true);
    expect(d.buttonText).toContain("7-Day Trial");
  });

  it("returns Launch pricing without setup fee", () => {
    const d = getCheckoutDisplay("basic");
    expect(d.monthly).toBe(1497);
    expect(d.setupFee).toBeNull();
    expect(d.includeSetupFee).toBe(false);
    expect(d.modalNote).toContain("No setup fee");
  });

  it("returns Scale pricing with custom suffix support", () => {
    const d = getCheckoutDisplay("pro_plus");
    expect(d.monthly).toBe(9997);
    expect(d.setupFee).toBe(1997);
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
    expect(formatSetupFee(1997)).toBe("$1,997 one-time setup");
  });
});