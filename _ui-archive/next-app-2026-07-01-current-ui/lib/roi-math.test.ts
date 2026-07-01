import { describe, expect, it } from "vitest";
import { buildOnboardingQueryFromRoi, computeRoi } from "./roi-math";

describe("computeRoi", () => {
  it("computes monthly revenue at risk from missed calls", () => {
    const r = computeRoi({ missedPerWeek: 10, avgJobValue: 500 });
    expect(r.recoveredMonthly).toBe(20000);
    expect(r.breakevenDays).toBe(3);
  });

  it("returns null breakeven when recovered is below plan cost", () => {
    const r = computeRoi({ missedPerWeek: 1, avgJobValue: 100 });
    expect(r.recoveredMonthly).toBe(400);
    expect(r.breakevenDays).toBeNull();
  });
});

describe("buildOnboardingQueryFromRoi", () => {
  it("feeds signup with calculator values", () => {
    const inputs = { missedPerWeek: 12, avgJobValue: 400 };
    const result = computeRoi(inputs);
    const q = buildOnboardingQueryFromRoi(result, inputs);
    expect(q).toContain("source=roi");
    expect(q).toContain("missed=12");
    expect(q).toContain("job_value=400");
    expect(q).toContain("recovered=19200");
  });
});