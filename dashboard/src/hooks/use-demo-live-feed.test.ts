import { describe, expect, it } from "vitest";
import { buildDemoLiveSnapshot } from "@/hooks/use-demo-live-feed";

describe("useDemoLiveFeed", () => {
  it("buildDemoLiveSnapshot seeds in-progress demo calls", () => {
    const snap = buildDemoLiveSnapshot(0);
    expect(snap.length).toBeGreaterThan(0);
    expect(snap[0].status).toBe("in_progress");
    expect(snap[0].reasoning).toBeTruthy();
  });

  it("buildDemoLiveSnapshot appends transcript ticks over time", () => {
    const a = buildDemoLiveSnapshot(0);
    const b = buildDemoLiveSnapshot(2);
    const lenA = a[0]?.transcript?.length ?? 0;
    const lenB = b[0]?.transcript?.length ?? 0;
    expect(lenB).toBeGreaterThanOrEqual(lenA);
  });
});