export interface Organization {
  id: string;
  name: string;
  industry: string;
  timezone: string;
  created_at: string;
}

export interface Profile {
  id: string;
  org_id: string;
  full_name: string;
  role: 'owner' | 'admin' | 'viewer';
  created_at: string;
}

export type PlanTier = 'basic' | 'pro' | 'pro_plus' | 'enterprise';

export interface Subscription {
  id: string;
  org_id: string;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  plan_tier: PlanTier;
  status: 'active' | 'trialing' | 'past_due' | 'canceled' | 'incomplete';
  current_period_end: string | null;
}

export interface Agent {
  id: string;
  org_id: string;
  voice_provider: 'retell' | 'vapi';
  provider_agent_id: string;
  phone_number: string;
  system_prompt: string;
  voice_id: string;
  greeting: string;
}

export type CallStatus = 'completed' | 'missed' | 'in_progress' | 'failed';

export interface CallTranscriptTurn {
  role: 'agent' | 'user';
  content: string;
  timestamp?: number;
}

export interface CallActionItems {
  is_emergency: boolean;
  appointment_booked: boolean;
  caller_name?: string;
  caller_phone?: string;
  caller_address?: string;
  appointment_datetime?: string;
  notes?: string;
}

export interface Call {
  id: string;
  org_id: string;
  agent_id: string;
  provider_call_id: string;
  caller_number: string;
  duration_seconds: number;
  status: CallStatus;
  recording_url: string | null;
  transcript: CallTranscriptTurn[] | null;
  summary: string | null;
  action_items: CallActionItems | null;
  created_at: string;
}

export const PLAN_DETAILS: Record<PlanTier, {
  name: string;
  price: number;
  callLimit: number;
  features: string[];
}> = {
  basic: {
    name: 'Launch',
    price: 1497,
    callLimit: 1500,
    features: ['Done-for-you AI call answering', 'Up to 1,500 calls/mo', 'Voicemail → text + email', 'Instant message alerts', '1 phone number', 'White-glove onboarding'],
  },
  pro: {
    name: 'Growth',
    price: 4997,
    callLimit: 5000,
    features: ['Everything in Launch', 'Up to 5,000 calls/mo', 'Appointment booking + calendar', 'CRM integration & call routing', 'Analytics dashboard · 3 numbers', 'Priority support'],
  },
  pro_plus: {
    name: 'Scale',
    price: 9997,
    callLimit: 15000,
    features: ['Everything in Growth', 'Up to 15,000 calls/mo', 'Advanced analytics', 'Multi-location workflows', 'Dedicated success lead', 'SLA options'],
  },
  enterprise: {
    name: 'Enterprise',
    price: 0,
    callLimit: -1,
    features: ['Multi-location', 'Advanced AI agents', 'White-label', 'Priority support + SLA', 'Dedicated onboarding'],
  },
};
