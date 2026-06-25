// ───────────────────────────────────────────────────────────
// Billing & Usage Types
// ───────────────────────────────────────────────────────────

import type { PlanType } from "./auth";

export interface Plan {
  id: PlanType;
  displayName: string;
  description: string;
  monthlyCalls: number;
  monthlyMinutes: number;
  teamMembers: number;
  integrations: number;
  features: string[];
  price: number;
}


export interface UsageStats {
  tenantId: string;
  periodStart: string;
  periodEnd: string;
  callsUsed: number;
  callsLimit: number;
  minutesUsed: number;
  minutesLimit: number;
  messagesReceived: number;
  appointmentsBooked: number;
  teamMembersUsed: number;
  teamMembersLimit: number;
  integrationsUsed: number;
  integrationsLimit: number;
  storageUsed: number;
  storageLimit: number;
}

export interface UsageHistoryRecord {
  date: string;
  calls: number;
  minutes: number;
  messages: number;
  appointments: number;
}

export const PLANS: Record<PlanType, Plan> = {
  free: {
    id: "free",
    displayName: "Free",
    description: "Perfect for trying out Owlbell",
    monthlyCalls: 50,
    monthlyMinutes: 300,
    teamMembers: 1,
    integrations: 1,
    features: [
      "AI call answering",
      "Basic call transcripts",
      "Message taking",
      "Email notifications",
      "50 calls/month",
    ],
    price: 0,
  },
  starter: {
    id: "starter",
    displayName: "Starter",
    description: "For small businesses with regular call volume",
    monthlyCalls: 200,
    monthlyMinutes: 1200,
    teamMembers: 3,
    integrations: 3,
    features: [
      "Everything in Free",
      "Appointment booking",
      "Custom AI greeting",
      "Call analytics",
      "Google Calendar sync",
      "Slack notifications",
      "200 calls/month",
    ],
    price: 29,
  },
  growth: {
    id: "growth",
    displayName: "Growth",
    description: "For growing businesses with higher call volume",
    monthlyCalls: 1000,
    monthlyMinutes: 6000,
    teamMembers: 10,
    integrations: 10,
    features: [
      "Everything in Starter",
      "Knowledge base",
      "CRM integrations",
      "Team management",
      "Priority support",
      "Custom voice persona",
      "1000 calls/month",
    ],
    price: 99,
  },
  enterprise: {
    id: "enterprise",
    displayName: "Enterprise",
    description: "Unlimited scale for large organizations",
    monthlyCalls: -1,
    monthlyMinutes: -1,
    teamMembers: -1,
    integrations: -1,
    features: [
      "Everything in Growth",
      "Unlimited calls",
      "Unlimited minutes",
      "Unlimited team members",
      "Unlimited integrations",
      "Custom AI training",
      "Dedicated support",
      "SLA guarantee",
      "On-premise option",
    ],
    price: 299,
  },
};
