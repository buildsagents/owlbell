import type { AnalyticsResponse } from "@/types/analytics";
import type { CallsResponse, Call } from "@/types/call";

const now = new Date();
const isoDaysAgo = (n: number) => {
  const d = new Date(now);
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
};

export const DEMO_ANALYTICS: AnalyticsResponse = {
  period: "week",
  dateRange: { from: isoDaysAgo(7), to: isoDaysAgo(0) },
  metrics: {
    totalCalls: 142,
    totalChange: 12,
    answeredCalls: 128,
    answeredChange: 8,
    missedCalls: 14,
    missedChange: -18,
    avgDuration: 186,
    avgDurationChange: 4,
    avgWaitTime: 1.8,
    avgWaitTimeChange: -22,
    resolutionRate: 0.87,
    resolutionRateChange: 5,
  },
  dailyData: Array.from({ length: 7 }, (_, i) => ({
    date: isoDaysAgo(6 - i),
    calls: 18 + (i % 4) * 3,
    answered: 16 + (i % 3) * 2,
    missed: 2 + (i % 2),
    avgDuration: 170 + i * 5,
  })),
  hourlyData: Array.from({ length: 24 }, (_, hour) => ({
    hour,
    calls: hour >= 8 && hour <= 18 ? 8 + (hour % 5) : 2 + (hour % 3),
    answered: hour >= 8 && hour <= 18 ? 7 + (hour % 4) : 2,
    missed: hour >= 20 || hour <= 6 ? 1 : 0,
  })),
  outcomeBreakdown: [
    { outcome: "appointment_booked", count: 48, percentage: 34 },
    { outcome: "question_answered", count: 52, percentage: 37 },
    { outcome: "transferred", count: 18, percentage: 13 },
    { outcome: "voicemail_left", count: 14, percentage: 10 },
    { outcome: "no_resolution", count: 10, percentage: 6 },
  ],
  topCallers: [
    { phoneNumber: "+15125550101", name: "Sarah M.", callCount: 4, totalDuration: 720 },
    { phoneNumber: "+15125550202", name: "James T.", callCount: 3, totalDuration: 540 },
    { phoneNumber: "+15125550303", name: null, callCount: 2, totalDuration: 310 },
  ],
};

function demoCall(i: number): Call {
  const started = new Date(now.getTime() - i * 3600_000);
  return {
    id: `demo-call-${i}`,
    tenantId: "demo",
    callerNumber: `+1512555${String(1000 + i).slice(-4)}`,
    callerName: i % 2 === 0 ? "Homeowner" : null,
    callerLocation: "Austin, TX",
    direction: "inbound",
    status: i === 0 ? "in_progress" : "completed",
    outcome: i % 3 === 0 ? "appointment_booked" : "question_answered",
    duration: 120 + i * 15,
    startedAt: started.toISOString(),
    endedAt: i === 0 ? null : new Date(started.getTime() + 120_000).toISOString(),
    recordingUrl: null,
    transcript: [
      { id: "1", speaker: "ai", text: "Thanks for calling — how can I help?", startTime: 0, endTime: 3, confidence: 0.98 },
      { id: "2", speaker: "caller", text: "I have a leak under my sink.", startTime: 3, endTime: 8, confidence: 0.95 },
    ],
    summary: "Leak under kitchen sink — booked tomorrow 9–11am.",
    aiAgentName: "Morgan",
    handledBy: "ai",
    transferredTo: null,
    tags: i % 2 === 0 ? ["emergency"] : ["standard"],
    notes: null,
    rating: null,
    createdAt: started.toISOString(),
  };
}

export const DEMO_CALLS: CallsResponse = {
  calls: Array.from({ length: 12 }, (_, i) => demoCall(i)),
  pagination: { page: 1, pageSize: 25, total: 12, totalPages: 1 },
  summary: { totalCalls: 12, answeredCount: 11, missedCount: 1, avgDuration: 165, totalDuration: 1980 },
};

export function shouldUseDemoData(): boolean {
  return import.meta.env.VITE_USE_DEMO_DATA === "true" || import.meta.env.DEV;
}