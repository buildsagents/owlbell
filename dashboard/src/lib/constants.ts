export const API_ENDPOINTS = {
  auth: {
    login: "/auth/login",
    signup: "/auth/signup",
    logout: "/auth/logout",
    refresh: "/auth/refresh",
    me: "/auth/me",
    mfaSetup: "/auth/mfa/setup",
    mfaVerify: "/auth/mfa/verify",
    mfaDisable: "/auth/mfa/disable",
    forgotPassword: "/auth/forgot-password",
    resetPassword: "/auth/reset-password",
    magicLink: "/auth/magic-link",
    magicLinkVerify: "/auth/magic-link/verify",
  },
  calls: {
    list: "/calls",
    detail: (id: string) => `/calls/${id}`,
    transcript: (id: string) => `/calls/${id}/transcript`,
    recording: (id: string) => `/calls/${id}/recording`,
    update: (id: string) => `/calls/${id}`,
    export: "/calls/export",
  },
  messages: {
    list: "/messages",
    detail: (id: string) => `/messages/${id}`,
    update: (id: string) => `/messages/${id}`,
    resolve: (id: string) => `/messages/${id}/resolve`,
    export: "/messages/export",
  },
  appointments: {
    list: "/appointments",
    detail: (id: string) => `/appointments/${id}`,
    create: "/appointments",
    update: (id: string) => `/appointments/${id}`,
    cancel: (id: string) => `/appointments/${id}/cancel`,
    availability: "/appointments/availability",
    blockedDates: "/appointments/blocked-dates",
  },
  analytics: {
    metrics: "/analytics/metrics",
    hourly: "/analytics/hourly",
    daily: "/analytics/daily",
    outcomes: "/analytics/outcomes",
    callers: "/analytics/top-callers",
    export: "/analytics/export",
  },
  settings: {
    ai: "/settings/ai",
    businessHours: "/settings/business-hours",
    faqs: "/settings/faqs",
    faqDetail: (id: string) => `/settings/faqs/${id}`,
  },
  knowledge: {
    documents: "/knowledge/documents",
    upload: "/knowledge/documents/upload",
    document: (id: string) => `/knowledge/documents/${id}`,
    reindex: (id: string) => `/knowledge/documents/${id}/reindex`,
  },
  integrations: {
    list: "/integrations",
    connect: (provider: string) => `/integrations/${provider}/connect`,
    disconnect: (provider: string) => `/integrations/${provider}/disconnect`,
    sync: (provider: string) => `/integrations/${provider}/sync`,
  },
  team: {
    members: "/team/members",
    invite: "/team/invite",
    member: (id: string) => `/team/members/${id}`,
    updateRole: (id: string) => `/team/members/${id}/role`,
    remove: (id: string) => `/team/members/${id}`,
    resendInvite: (id: string) => `/team/members/${id}/resend-invite`,
  },
  billing: {
    usage: "/billing/usage",
    plan: "/billing/plan",
    history: "/billing/history",
  },
  notifications: {
    list: "/notifications",
    markRead: (id: string) => `/notifications/${id}/read`,
    markAllRead: "/notifications/read-all",
    preferences: "/notifications/preferences",
  },
  agency: {
    overview: "/agency/overview",
    clients: "/agency/clients",
    client: (id: string) => `/agency/clients/${id}`,
    advanceOnboarding: (id: string) => `/agency/clients/${id}/onboarding/advance`,
    onboardingPipeline: "/agency/onboarding/pipeline",
  },
  phoneNumbers: {
    available: "/phone-numbers/available",
    assign: "/phone-numbers/assign",
    list: "/phone-numbers",
  },
  leads: {
    all: "/leads/all",
    stats: "/leads/stats",
    run: "/leads/run",
    checkReplies: "/leads/check-replies",
  },
} as const;

export interface NavItem {
  label: string;
  path: string;
  icon: string;
  badge?: "active_calls" | "unread_messages";
  children?: NavItem[];
  requiredPermission?: string;
}

export const MAIN_NAVIGATION: NavItem[] = [
  { label: "Dashboard", path: "/dashboard", icon: "layout-dashboard" },
  { label: "Calls", path: "/calls", icon: "phone", badge: "active_calls" },
  { label: "Analytics", path: "/analytics", icon: "bar-chart-3" },
  { label: "Messages", path: "/messages", icon: "message-square", badge: "unread_messages" },
  { label: "Appointments", path: "/appointments", icon: "calendar-days" },
];

export const SETTINGS_NAVIGATION: NavItem[] = [
  { label: "AI Personality", path: "/settings/ai-personality", icon: "bot" },
  { label: "Business Hours", path: "/settings/business-hours", icon: "clock" },
  { label: "Knowledge Base", path: "/settings/knowledge-base", icon: "book-open" },
  { label: "Integrations", path: "/settings/integrations", icon: "plug" },
  { label: "Notifications", path: "/settings/notifications", icon: "bell" },
];

export const ADMIN_NAVIGATION: NavItem[] = [
  { label: "Team", path: "/team", icon: "users", requiredPermission: "team:read" },
  { label: "Billing", path: "/billing", icon: "credit-card", requiredPermission: "billing:read" },
];

export const OUTREACH_NAVIGATION: NavItem[] = [
  { label: "Outreach", path: "/outreach", icon: "send" },
];

export const AGENCY_NAVIGATION: NavItem[] = [
  { label: "Agency Overview", path: "/agency", icon: "layout-dashboard" },
  { label: "Clients", path: "/agency/clients", icon: "users" },
  { label: "Provision Client", path: "/agency/provision", icon: "user-plus" },
  { label: "Onboarding", path: "/agency/onboarding", icon: "layers" },
];
