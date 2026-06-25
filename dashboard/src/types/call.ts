// ───────────────────────────────────────────────────────────
// Call Types
// ───────────────────────────────────────────────────────────

export type CallStatus =
  | "ringing"
  | "in_progress"
  | "completed"
  | "missed"
  | "voicemail"
  | "transferred"
  | "failed";

export type CallDirection = "inbound" | "outbound";

export type CallOutcome =
  | "message_taken"
  | "appointment_booked"
  | "question_answered"
  | "transferred"
  | "voicemail_left"
  | "hangup"
  | "spam"
  | "no_resolution";

export interface TranscriptSegment {
  id: string;
  speaker: "ai" | "caller";
  text: string;
  startTime: number;
  endTime: number;
  confidence: number;
}

export interface Call {
  id: string;
  tenantId: string;
  callerNumber: string;
  callerName: string | null;
  callerLocation: string | null;
  direction: CallDirection;
  status: CallStatus;
  outcome: CallOutcome | null;
  duration: number;
  startedAt: string;
  endedAt: string | null;
  recordingUrl: string | null;
  transcript: TranscriptSegment[] | null;
  summary: string | null;
  aiAgentName: string;
  handledBy: "ai" | "human";
  transferredTo: string | null;
  tags: string[];
  notes: string | null;
  rating: number | null;
  createdAt: string;
}

export interface ActiveCall extends Call {
  status: "ringing" | "in_progress";
  currentTranscript: TranscriptSegment[];
  audioLevel: number;
  elapsedTime: number;
}

export interface CallFilters {
  status?: CallStatus | null;
  direction?: CallDirection | null;
  outcome?: CallOutcome | null;
  dateFrom?: string | null;
  dateTo?: string | null;
  callerNumber?: string | null;
  search?: string | null;
  tags?: string[];
}

export interface CallPagination {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface CallsResponse {
  calls: Call[];
  pagination: CallPagination;
  summary: {
    totalCalls: number;
    totalDuration: number;
    avgDuration: number;
    answeredCount: number;
    missedCount: number;
  };
}
