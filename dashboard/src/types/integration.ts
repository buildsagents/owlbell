// ───────────────────────────────────────────────────────────
// Integration Types
// ───────────────────────────────────────────────────────────

export type IntegrationProvider =
  | "google_calendar"
  | "outlook_calendar"
  | "slack"
  | "hubspot"
  | "salesforce"
  | "zapier"
  | "webhook"
  | "twilio"
  | "sendgrid"
  | "mailchimp";

export type IntegrationStatus = "connected" | "disconnected" | "error" | "pending";

export interface Integration {
  id: string;
  tenantId: string;
  provider: IntegrationProvider;
  status: IntegrationStatus;
  config: Record<string, unknown> | null;
  connectedAt: string | null;
  disconnectedAt: string | null;
  lastSyncAt: string | null;
  errorMessage: string | null;
  metadata: IntegrationMetadata | null;
}

export interface IntegrationMetadata {
  accountEmail?: string;
  accountName?: string;
  workspaceName?: string;
  channelName?: string;
  calendarName?: string;
}

export interface IntegrationProviderConfig {
  provider: IntegrationProvider;
  displayName: string;
  description: string;
  icon: string;
  category: "calendar" | "crm" | "communication" | "automation" | "email";
  oauthUrl: string;
  scopes: string[];
  features: string[];
}

export const INTEGRATION_PROVIDERS: IntegrationProviderConfig[] = [
  {
    provider: "google_calendar",
    displayName: "Google Calendar",
    description: "Sync AI-booked appointments to your Google Calendar",
    icon: "calendar",
    category: "calendar",
    oauthUrl: "/api/v1/integrations/google/auth",
    scopes: ["calendar.events", "calendar.readonly"],
    features: ["auto-sync appointments", "block availability", "event updates"],
  },
  {
    provider: "slack",
    displayName: "Slack",
    description: "Get real-time call notifications in Slack",
    icon: "message-square",
    category: "communication",
    oauthUrl: "/api/v1/integrations/slack/auth",
    scopes: ["chat:write", "channels:read"],
    features: ["call alerts", "message notifications", "daily summaries"],
  },
  {
    provider: "hubspot",
    displayName: "HubSpot",
    description: "Sync call data and messages to HubSpot CRM",
    icon: "database",
    category: "crm",
    oauthUrl: "/api/v1/integrations/hubspot/auth",
    scopes: ["contacts", "timeline"],
    features: ["contact sync", "call logging", "deal creation"],
  },
  {
    provider: "zapier",
    displayName: "Zapier",
    description: "Connect to 5000+ apps via Zapier",
    icon: "zap",
    category: "automation",
    oauthUrl: "/api/v1/integrations/zapier/auth",
    scopes: ["triggers", "actions"],
    features: ["custom workflows", "multi-app integrations", "automated actions"],
  },
  {
    provider: "webhook",
    displayName: "Custom Webhook",
    description: "Send call events to your own HTTP endpoints",
    icon: "webhook",
    category: "automation",
    oauthUrl: "",
    scopes: [],
    features: ["real-time events", "custom payloads", "retry logic"],
  },
];
