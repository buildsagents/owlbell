// ───────────────────────────────────────────────────────────
// AI Settings Types
// ───────────────────────────────────────────────────────────

export type VoicePersona = "professional" | "friendly" | "warm" | "energetic" | "calm";

export type VoiceGender = "female" | "male" | "neutral";

export type AiModel = "llama3.1:8b" | "llama3.1:70b" | "mixtral:8x7b";

export interface AiSettings {
  tenantId: string;
  greeting: string;
  farewell: string;
  voicePersona: VoicePersona;
  voiceGender: VoiceGender;
  voiceSpeed: number;
  aiModel: AiModel;
  maxCallDuration: number;
  transferEnabled: boolean;
  voicemailEnabled: boolean;
  appointmentBookingEnabled: boolean;
  messageTakingEnabled: boolean;
  language: string;
  customInstructions: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface BusinessHours {
  id: string;
  tenantId: string;
  dayOfWeek: 0 | 1 | 2 | 3 | 4 | 5 | 6;
  openTime: string;
  closeTime: string;
  isOpen: boolean;
  is24Hours: boolean;
}

export interface FaqEntry {
  id: string;
  tenantId: string;
  question: string;
  answer: string;
  category: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface KnowledgeDocument {
  id: string;
  tenantId: string;
  filename: string;
  originalName: string;
  fileType: "pdf" | "csv" | "txt" | "docx" | "md";
  fileSize: number;
  status: "uploading" | "processing" | "indexed" | "failed";
  chunkCount: number | null;
  errorMessage: string | null;
  uploadedBy: string;
  createdAt: string;
  updatedAt: string;
}
