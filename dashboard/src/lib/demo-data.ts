import type { AnalyticsResponse } from "@/types/analytics";
import type { CallsResponse, Call } from "@/types/call";
import type { Message } from "@/types/message";

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
      { id: "1", speaker: "ai", text: "Thanks for calling. How can I help?", startTime: 0, endTime: 3, confidence: 0.98 },
      { id: "2", speaker: "caller", text: "I have a leak under my sink.", startTime: 3, endTime: 8, confidence: 0.95 },
    ],
    summary: "Leak under kitchen sink - booked tomorrow 9-11am.",
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

export const DEMO_MESSAGES: Message[] = [
  {
    id: "demo-msg-1",
    tenantId: "demo",
    callId: "demo-call-2",
    callerName: "James T.",
    callerNumber: "+15125550202",
    callerEmail: null,
    subject: "Water heater quote",
    body: "Caller requested estimate for 40-gal replacement. Callback preferred after 3pm.",
    status: "new",
    priority: "medium",
    assignedTo: null,
    tags: ["quote"],
    createdAt: new Date(now.getTime() - 2 * 3600_000).toISOString(),
    resolvedAt: null,
    resolvedBy: null,
    notes: null,
  },
  {
    id: "demo-msg-2",
    tenantId: "demo",
    callId: "demo-call-4",
    callerName: null,
    callerNumber: "+15125550404",
    callerEmail: "homeowner@example.com",
    subject: "Emergency leak - after hours",
    body: "Active leak under kitchen sink. AI escalated to on-call; SMS sent to owner.",
    status: "in_progress",
    priority: "urgent",
    assignedTo: null,
    tags: ["emergency"],
    createdAt: new Date(now.getTime() - 45 * 60_000).toISOString(),
    resolvedAt: null,
    resolvedBy: null,
    notes: "Waiting for tech callback",
  },
  {
    id: "demo-msg-3",
    tenantId: "demo",
    callId: null,
    callerName: "Sarah M.",
    callerNumber: "+15125550101",
    callerEmail: null,
    subject: "Reschedule appointment",
    body: "Needs to move Thursday 9am slot to Friday morning.",
    status: "resolved",
    priority: "low",
    assignedTo: null,
    tags: ["scheduling"],
    createdAt: new Date(now.getTime() - 26 * 3600_000).toISOString(),
    resolvedAt: new Date(now.getTime() - 24 * 3600_000).toISOString(),
    resolvedBy: "owner",
    notes: null,
  },
];

export const DEMO_AGENCY_OVERVIEW = {
  totalClients: 24,
  activeClients: 19,
  trialClients: 5,
  totalCallsThisMonth: 6842,
  totalCallsLastMonth: 5210,
  mrr: 28340,
  arr: 340080,
  avgCallsPerClient: 285,
  topIndustries: [
    { industry: "Plumbing", count: 9 },
    { industry: "HVAC", count: 6 },
    { industry: "Electrical", count: 4 },
  ],
  onboardingPipeline: {
    intake: 5,
    build: 4,
    phone: 3,
    qa: 2,
    live: 19,
  },
};

export const DEMO_AGENCY_CLIENTS = [
  {
    id: "arctic-air",
    slug: "arctic-air",
    name: "Arctic Air & Heat",
    plan: "professional",
    status: "active",
    industry: "HVAC",
    phone: "+15125550111",
    createdAt: isoDaysAgo(44),
    callsThisMonth: 486,
    callsLastMonth: 402,
    revenueMtd: 797,
    onboardingStep: 8,
    onboardingComplete: true,
  },
  {
    id: "metro-plumbing",
    slug: "metro-plumbing",
    name: "Metro Emergency Plumbing",
    plan: "pro_plus",
    status: "active",
    industry: "Plumbing",
    phone: "+15125550122",
    createdAt: isoDaysAgo(29),
    callsThisMonth: 732,
    callsLastMonth: 590,
    revenueMtd: 1497,
    onboardingStep: 8,
    onboardingComplete: true,
  },
  {
    id: "brightline-electrical",
    slug: "brightline-electrical",
    name: "Brightline Electrical",
    plan: "professional",
    status: "trial",
    industry: "Electrical",
    phone: "+15125550133",
    createdAt: isoDaysAgo(8),
    callsThisMonth: 118,
    callsLastMonth: 0,
    revenueMtd: 797,
    onboardingStep: 5,
    onboardingComplete: false,
  },
  {
    id: "oak-dental",
    slug: "oak-dental",
    name: "Oak Street Dental",
    plan: "starter",
    status: "trial",
    industry: "Dental",
    phone: "+15125550144",
    createdAt: isoDaysAgo(4),
    callsThisMonth: 64,
    callsLastMonth: 0,
    revenueMtd: 297,
    onboardingStep: 3,
    onboardingComplete: false,
  },
  {
    id: "rapid-rooter",
    slug: "rapid-rooter",
    name: "Rapid Rooter Pros",
    plan: "enterprise",
    status: "active",
    industry: "Plumbing",
    phone: "+15125550155",
    createdAt: isoDaysAgo(71),
    callsThisMonth: 1044,
    callsLastMonth: 911,
    revenueMtd: 2000,
    onboardingStep: 8,
    onboardingComplete: true,
  },
];

export const DEMO_ONBOARDING_STEPS = [
  { step: 1, name: "Client intake", description: "Capture services, service areas, escalation contacts, and booking rules." },
  { step: 2, name: "Voice profile", description: "Choose voice, pace, greeting, objection handling, and emergency tone." },
  { step: 3, name: "Knowledge build", description: "Load FAQs, pricing guardrails, job types, and disqualifiers." },
  { step: 4, name: "Phone routing", description: "Assign number, forwarding, call recording, and failover rules." },
  { step: 5, name: "Calendar and CRM", description: "Connect booking, lead capture, SMS, and owner notifications." },
  { step: 6, name: "QA call review", description: "Run test calls and tune awkward replies before going live." },
  { step: 7, name: "Launch approval", description: "Confirm client signoff, emergency paths, and reporting cadence." },
  { step: 8, name: "Live optimization", description: "Monitor calls, add winning phrases, and improve booked-job rate." },
];

export const DEMO_ONBOARDING_PIPELINE = {
  steps: DEMO_ONBOARDING_STEPS,
  clients: DEMO_AGENCY_CLIENTS.map((client) => ({
    clientId: client.id,
    name: client.name,
    slug: client.slug,
    currentStep: client.onboardingStep,
    totalSteps: 8,
    complete: client.onboardingComplete,
    currentStepName:
      DEMO_ONBOARDING_STEPS[Math.max(0, Math.min(7, client.onboardingStep - 1))]?.name ?? "Client intake",
  })),
};

export function getDemoAgencyClient(id: string) {
  const client = DEMO_AGENCY_CLIENTS.find((item) => item.id === id) ?? DEMO_AGENCY_CLIENTS[0];
  return {
    ...client,
    email: `ops@${client.slug}.example`,
    timezone: "America/New_York",
    greeting: `Thanks for calling ${client.name}. This is Morgan. How can I help today?`,
    onboarding: DEMO_ONBOARDING_STEPS.map((step) => ({
      ...step,
      completed: client.onboardingComplete || step.step <= client.onboardingStep,
      completedAt: client.onboardingComplete || step.step <= client.onboardingStep ? isoDaysAgo(8 - step.step) : null,
    })),
    avgAnswerTime: 1.6,
    bookingRate: client.status === "active" ? 0.42 : 0.31,
  };
}

export function shouldUseDemoData(): boolean {
  return import.meta.env.VITE_USE_DEMO_DATA === "true" || import.meta.env.DEV;
}
