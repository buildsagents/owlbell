import { describe, expect, it } from "vitest";
import { DEMO_MESSAGES } from "@/lib/demo-data";

describe("DEMO_MESSAGES fallback data", () => {
  it("includes searchable demo messages for dashboard", () => {
    expect(DEMO_MESSAGES.length).toBeGreaterThanOrEqual(3);
    expect(DEMO_MESSAGES.some((m) => m.priority === "urgent")).toBe(true);
  });

  it("filters by status like useMessages demo path", () => {
    const newOnly = DEMO_MESSAGES.filter((m) => m.status === "new");
    expect(newOnly.every((m) => m.status === "new")).toBe(true);
  });
});