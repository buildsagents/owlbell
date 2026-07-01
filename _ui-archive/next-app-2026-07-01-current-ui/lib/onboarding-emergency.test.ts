import { describe, expect, it } from "vitest";
import { emergencyPayloadFromRouting } from "./onboarding-emergency";

describe("emergencyPayloadFromRouting", () => {
  it("maps 24/7 escalate to yes", () => {
    expect(emergencyPayloadFromRouting("escalate_emergency")).toEqual({
      emergency: "yes",
      emergencyRouting: "escalate_emergency",
    });
  });

  it("maps book next slot", () => {
    expect(emergencyPayloadFromRouting("book_next_slot")).toEqual({
      emergency: "book_next",
      emergencyRouting: "book_next_slot",
    });
  });

  it("maps business hours only", () => {
    expect(emergencyPayloadFromRouting("business_hours")).toEqual({
      emergency: "no",
      emergencyRouting: "business_hours",
    });
  });
});