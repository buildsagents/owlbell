// ───────────────────────────────────────────────────────────
// Real-Time Notification Types
// ───────────────────────────────────────────────────────────

export type NotificationType =
  | "call_incoming"
  | "call_completed"
  | "call_missed"
  | "message_received"
  | "appointment_booked"
  | "appointment_cancelled"
  | "team_invite"
  | "usage_warning"
  | "usage_limit"
  | "integration_error"
  | "system";

export type NotificationSeverity = "info" | "success" | "warning" | "error";

export interface Notification {
  id: string;
  tenantId: string;
  userId: string | null;
  type: NotificationType;
  severity: NotificationSeverity;
  title: string;
  body: string;
  data: Record<string, unknown> | null;
  isRead: boolean;
  readAt: string | null;
  createdAt: string;
}

export type WebSocketEventType =
  | "call_started"
  | "call_updated"
  | "call_ended"
  | "transcript_updated"
  | "message_received"
  | "appointment_updated"
  | "notification_created"
  | "usage_updated"
  | "ping"
  | "pong"
  | "auth_success"
  | "auth_error"
  | "subscribed"
  | "unsubscribed";

export interface WebSocketMessage {
  type: WebSocketEventType;
  payload: unknown;
  timestamp: string;
  tenantId: string;
}

export interface NotificationPreferences {
  userId: string;
  tenantId: string;
  emailEnabled: boolean;
  pushEnabled: boolean;
  smsEnabled: boolean;
  slackEnabled: boolean;
  callCompleted: boolean;
  callMissed: boolean;
  messageReceived: boolean;
  appointmentBooked: boolean;
  usageWarning: boolean;
  teamInvite: boolean;
  quietHoursStart: string | null;
  quietHoursEnd: string | null;
  quietHoursEnabled: boolean;
}
