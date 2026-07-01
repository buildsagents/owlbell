export interface OnboardingData {
  step1_businessInfo: {
    companyName: string;
    ownerName: string;
    email: string;
    mobile: string;
    businessAddress: string;
    website: string;
  };
  step2_businessDetails: {
    openingHours: string;
    emergencyAvailable: boolean;
    serviceAreas: string;
    servicesOffered: string[];
    typicalPricing: string;
    numberOfEngineers: number;
    preferredGreeting: string;
  };
  step3_callHandling: {
    bookingRules: string;
    emergencyRouting: string;
    outOfHoursBehavior: string;
    transferNumbers: string[];
    voicemailPreferences: string;
  };
  step4_calendar: {
    provider: '' | 'google' | 'microsoft';
    appointmentDuration: number;
    bufferTime: number;
  };
  step5_knowledgeBase: {
    faqs: string;
    priceList: string;
    serviceInfo: string;
    policies: string;
    websiteUrl: string;
  };
  step6_phoneNumbers: {
    type: 'new' | 'port';
    desiredNumber: string;
    existingNumber: string;
    forwardingConfigured: boolean;
  };
  step7_aiVoice: {
    voiceId: string;
    voiceName: string;
    speakingStyle: string;
  };
}

export const DEFAULT_ONBOARDING: OnboardingData = {
  step1_businessInfo: { companyName: '', ownerName: '', email: '', mobile: '', businessAddress: '', website: '' },
  step2_businessDetails: { openingHours: 'Mon-Fri 8:00-17:00', emergencyAvailable: true, serviceAreas: '', servicesOffered: [], typicalPricing: '', numberOfEngineers: 1, preferredGreeting: 'Thanks for calling {company}, this is {name}. Are you calling about an emergency or would you like to book a visit?' },
  step3_callHandling: { bookingRules: '', emergencyRouting: 'escalate_emergency', outOfHoursBehavior: 'voicemail', transferNumbers: [], voicemailPreferences: '' },
  step4_calendar: { provider: '', appointmentDuration: 60, bufferTime: 15 },
  step5_knowledgeBase: { faqs: '', priceList: '', serviceInfo: '', policies: '', websiteUrl: '' },
  step6_phoneNumbers: { type: 'new', desiredNumber: '', existingNumber: '', forwardingConfigured: false },
  step7_aiVoice: { voiceId: '', voiceName: '', speakingStyle: 'professional' },
};

export const STEPS = [
  { key: 'step1_businessInfo', label: 'Client basics', description: 'Company, owner, and contact details' },
  { key: 'step2_businessDetails', label: 'Service rules', description: 'Hours, coverage, pricing, and services' },
  { key: 'step3_callHandling', label: 'Call routing', description: 'Emergency handling and escalation' },
  { key: 'step4_calendar', label: 'Booking logic', description: 'Availability, slot length, and buffers' },
  { key: 'step5_knowledgeBase', label: 'Knowledge base', description: 'FAQs, pricing, policies, and website' },
  { key: 'step6_phoneNumbers', label: 'Forwarding', description: 'New number, porting, or overflow setup' },
  { key: 'step7_aiVoice', label: 'Voice and style', description: 'Receptionist voice and pacing' },
  { key: 'step8_review', label: 'Build review', description: 'Confirm before test calls' },
] as const;

export const SERVICE_OPTIONS = [
  'Burst pipe repair',
  'Blocked drains',
  'Boiler repair',
  'Radiator bleeding',
  'Tap repair',
  'Toilet repair',
  'Shower installation',
  'Central heating',
  'Gas safety checks',
  'Emergency callout',
] as const;

export const VOICE_OPTIONS = [
  { id: '79a125e8-cd45-4c13-8a67-188112f4dd22', name: 'Morgan', style: 'Warm, steady, concise emergency intake' },
  { id: 'f982d1e4-e8b0-4a9e-b8db-2d8c7a4321ab', name: 'Alex', style: 'Friendly, direct, good for smaller local firms' },
  { id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890', name: 'Sam', style: 'Calm, neutral, minimal filler' },
] as const;
