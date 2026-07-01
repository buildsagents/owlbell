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

export type PlanTier = 'basic' | 'pro' | 'pro_plus';

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
  voice_provider: 'retell';
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
  setupFee: number | null;
  features: string[];
}> = {
  basic: {
    name: 'Launch',
    price: 1497,
    setupFee: null,
    features: [
      'AI receptionist trained on your business - configured in onboarding',
      '24/7 call answering, lead capture, and owner alerts',
      'One number or call-forwarding setup',
      'Emergency routing rules',
      'Script tuning during first 30 days',
    ],
  },
  pro: {
    name: 'Growth',
    price: 4997,
    setupFee: 5000,
    features: [
      'Everything in Launch',
      'Calendar booking and missed-call recovery',
      'CRM or job-management handoff',
      'Advanced after-hours and emergency routing',
      'Monthly revenue review and conversion tuning',
      'Priority support with dedicated success contact',
    ],
  },
  pro_plus: {
    name: 'Scale',
    price: 9997,
    setupFee: 10000,
    features: [
      'Everything in Growth',
      'Multiple locations, numbers, and routing trees',
      'Custom reporting, SLAs, and escalation paths',
      'Dedicated success lead and quarterly workflow rebuilds',
      'Volume pricing for large rollouts',
    ],
  },
};
