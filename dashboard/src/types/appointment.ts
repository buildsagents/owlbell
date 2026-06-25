// ───────────────────────────────────────────────────────────
// Appointment Types
// ───────────────────────────────────────────────────────────

export type AppointmentStatus =
  | "scheduled"
  | "confirmed"
  | "completed"
  | "cancelled"
  | "no_show";

export interface Appointment {
  id: string;
  tenantId: string;
  callId: string | null;
  customerName: string;
  customerPhone: string;
  customerEmail: string | null;
  title: string;
  description: string | null;
  status: AppointmentStatus;
  scheduledAt: string;
  duration: number;
  timezone: string;
  calendarEventId: string | null;
  location: string | null;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface AvailabilitySlot {
  id: string;
  tenantId: string;
  dayOfWeek: 0 | 1 | 2 | 3 | 4 | 5 | 6;
  startTime: string;
  endTime: string;
  isActive: boolean;
}

export interface BlockedDate {
  id: string;
  tenantId: string;
  date: string;
  reason: string | null;
}
