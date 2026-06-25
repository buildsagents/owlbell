// ───────────────────────────────────────────────────────────
// Message Types (AI-taken messages)
// ───────────────────────────────────────────────────────────

export type MessageStatus = "new" | "in_progress" | "resolved" | "archived";

export type MessagePriority = "low" | "medium" | "high" | "urgent";

export interface Message {
  id: string;
  tenantId: string;
  callId: string | null;
  callerName: string | null;
  callerNumber: string;
  callerEmail: string | null;
  subject: string | null;
  body: string;
  status: MessageStatus;
  priority: MessagePriority;
  assignedTo: string | null;
  tags: string[];
  createdAt: string;
  resolvedAt: string | null;
  resolvedBy: string | null;
  notes: string | null;
}

export interface MessageFilters {
  status?: MessageStatus | null;
  priority?: MessagePriority | null;
  assignedTo?: string | null;
  dateFrom?: string | null;
  dateTo?: string | null;
  search?: string | null;
}
