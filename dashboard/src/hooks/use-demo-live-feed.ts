import { useEffect, useMemo, useState } from "react";
import { DEMO_CALLS } from "@/lib/demo-data";
import type { Call } from "@/types/call";

const REASONING_STEPS = [
  "Detect urgency from caller description",
  "Qualify service area and property type",
  "Offer next available appointment window",
  "Confirm contact details and dispatch note",
];

export type DemoLiveCall = Call & { reasoning: string };

export function buildDemoLiveSnapshot(tick: number): DemoLiveCall[] {
  const inProgress = DEMO_CALLS.calls.filter(
    (c) => c.status === "in_progress" || c.status === "ringing",
  );
  const reasoning = REASONING_STEPS[tick % REASONING_STEPS.length];

  return inProgress.map((call, index) => {
    const transcript = [...(call.transcript ?? [])];
    if (tick > 0 && tick % 2 === index % 2) {
      transcript.push({
        id: `demo-live-${tick}`,
        speaker: tick % 4 === 0 ? "ai" : "caller",
        text:
          tick % 4 === 0
            ? "I can get a technician out tomorrow between 9 and 11."
            : "That works. My address is 123 Oak Street.",
        startTime: 10 + tick,
        endTime: 14 + tick,
        confidence: 0.96,
      });
    }
    return { ...call, transcript, reasoning };
  });
}

export function useDemoLiveFeed() {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 3000);
    return () => window.clearInterval(id);
  }, []);

  const calls = useMemo(() => buildDemoLiveSnapshot(tick), [tick]);

  return { calls, tick, isDemo: true as const };
}
