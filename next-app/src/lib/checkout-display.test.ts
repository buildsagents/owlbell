import { describe, expect, it } from "vitest";
import {
  FOUNDING_SLOTS,
  formatMonthlyPrice,
  foundingSlotsFillPercent,
  foundingThreeMonthSavings,
  getCheckoutDisplay,
  normalizePlanId,
} from "./checkout-display";

describe("getCheckoutDisplay", () => {
  it("returns standard Growth price when founding is false", () => {
    const d = getCheckoutDisplay("pro", false);
    expect(d.monthly).toBe(4997);
    expect(d.buttonText).toContain("4997");
    expect(d.foundingNote).toBeNull();
  });

  it("returns founding Growth price when founding is true", () => {
    const d = getCheckoutDisplay("pro", true);
    expect(d.monthly).toBe(3997);
    expect(d.buttonText).toContain("3997");
    expect(d.foundingNote).toContain("FOUNDING50");
  });

  it("returns founding Launch price for basic founding checkout", () => {
    const d = getCheckoutDisplay("basic", true);
    expect(d.monthly).toBe(997);
  });

  it("normalizes unknown plan to pro", () => {
    expect(normalizePlanId("unknown")).toBe("pro");
  });
});

describe("foundingSlotsFillPercent", () => {
  it("computes bar fill from remaining/total slots", () => {
    expect(foundingSlotsFillPercent()).toBe((FOUNDING_SLOTS.remaining / FOUNDING_SLOTS.total) * 100);
  });
});

describe("formatMonthlyPrice", () => {
  it("formats founding Growth rate for UI", () => {
    expect(formatMonthlyPrice(getCheckoutDisplay("pro", true).monthly)).toBe("$3997/mo");
  });

  it("formats founding Launch rate for UI", () => {
    expect(formatMonthlyPrice(getCheckoutDisplay("basic", true).monthly)).toBe("$997/mo");
  });
});

describe("foundingThreeMonthSavings", () => {
  it("computes Growth first-3-month savings from rate delta", () => {
    expect(foundingThreeMonthSavings("pro")).toBe(3000);
  });
});
