/** Maps wizard emergencyRouting values to API intake fields. */

export function emergencyPayloadFromRouting(routing: string): {
  emergency: string;
  emergencyRouting: string;
} {
  switch (routing) {
    case "escalate_emergency":
      return { emergency: "yes", emergencyRouting: "escalate_emergency" };
    case "book_next_slot":
      return { emergency: "book_next", emergencyRouting: "book_next_slot" };
    case "business_hours":
      return { emergency: "no", emergencyRouting: "business_hours" };
    default:
      return { emergency: "yes", emergencyRouting: routing || "escalate_emergency" };
  }
}