export interface CallRecord {
  id: string;
  callerNumber: string;
  callerName: string;
  duration: number;
  status: 'completed' | 'missed' | 'in_progress' | 'failed';
  timestamp: string;
  summary: string;
  recordingUrl?: string;
}

export interface DashboardStats {
  totalCalls: number;
  answeredCalls: number;
  missedCalls: number;
  appointmentsBooked: number;
  avgResponseTime: number;
  activeSince: string;
}

export interface AlertItem {
  id: string;
  type: 'emergency' | 'missed' | 'system';
  message: string;
  timestamp: string;
  read: boolean;
}

export interface AgentConfig {
  greeting: string;
  systemPrompt: string;
  voiceId: string;
  voiceName: string;
  businessHours: string;
  emergencyRouting: string;
}

export interface SubscriptionInfo {
  plan: string;
  status: 'active' | 'trialing' | 'past_due' | 'canceled';
  nextBilling: string;
  amount: number;
  customerId?: string;
}

export const MOCK_STATS: DashboardStats = {
  totalCalls: 847,
  answeredCalls: 812,
  missedCalls: 35,
  appointmentsBooked: 203,
  avgResponseTime: 4.2,
  activeSince: 'Jan 2025',
};

export const MOCK_CALLS: CallRecord[] = [
  { id: '1', callerNumber: '+44 7700 900123', callerName: 'James Wilson', duration: 184, status: 'completed', timestamp: '2026-06-29T09:23:00Z', summary: 'Burst pipe emergency - dispatched to on-call team', recordingUrl: '' },
  { id: '2', callerNumber: '+44 7700 900456', callerName: 'Sarah Chen', duration: 312, status: 'completed', timestamp: '2026-06-29T08:45:00Z', summary: 'Blocked drain - booked for tomorrow 10:00 AM', recordingUrl: '' },
  { id: '3', callerNumber: '+44 7700 900789', callerName: 'David Brown', duration: 97, status: 'completed', timestamp: '2026-06-28T17:30:00Z', summary: 'Boiler pressure query - answered, no appointment needed' },
  { id: '4', callerNumber: '+44 7700 900012', callerName: 'Emma Davis', duration: 0, status: 'missed', timestamp: '2026-06-28T16:15:00Z', summary: 'Call dropped after 30s - no callback number captured' },
  { id: '5', callerNumber: '+44 7700 900345', callerName: 'Tom Harris', duration: 256, status: 'completed', timestamp: '2026-06-28T14:00:00Z', summary: 'Radiator not heating - booked for Friday 2:00 PM' },
  { id: '6', callerNumber: '+44 7700 900678', callerName: 'Lisa Patel', duration: 0, status: 'failed', timestamp: '2026-06-28T11:20:00Z', summary: 'System error - caller disconnected during transfer' },
  { id: '7', callerNumber: '+44 7700 900901', callerName: 'Mark Taylor', duration: 145, status: 'completed', timestamp: '2026-06-27T19:45:00Z', summary: 'Emergency - gas smell reported, immediate team dispatch' },
  { id: '8', callerNumber: '+44 7700 900234', callerName: 'Rachel Green', duration: 89, status: 'completed', timestamp: '2026-06-27T10:30:00Z', summary: 'Tap dripping - booked for next Wednesday AM' },
];

export const MOCK_ALERTS: AlertItem[] = [
  { id: 'a1', type: 'emergency', message: 'Emergency call routed - burst pipe at 24 Maple Road', timestamp: '2026-06-29T09:23:00Z', read: false },
  { id: 'a2', type: 'missed', message: 'Missed call from +44 7700 900012 - no callback info', timestamp: '2026-06-28T16:15:00Z', read: false },
  { id: 'a3', type: 'system', message: 'Retell agent usage at 94% of monthly limit', timestamp: '2026-06-28T08:00:00Z', read: true },
];

export const MOCK_SUBSCRIPTION: SubscriptionInfo = {
  plan: 'Growth',
  status: 'active',
  nextBilling: '2026-07-15',
  amount: 4997,
};

export const MOCK_AGENT_CONFIG: AgentConfig = {
  greeting: 'Thanks for calling {company}, this is Morgan. Are you calling about an emergency, or would you like to book a visit?',
  systemPrompt: 'You are a warm, concise receptionist for a UK plumbing company...',
  voiceId: '79a125e8-cd45-4c13-8a67-188112f4dd22',
  voiceName: 'Morgan',
  businessHours: 'Mon-Fri 8:00-17:00',
  emergencyRouting: 'Escalate to on-call team',
};
