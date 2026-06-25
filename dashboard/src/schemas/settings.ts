import { z } from "zod";

export const aiSettingsSchema = z.object({
  greeting: z.string().max(500, "Greeting must be 500 characters or less"),
  farewell: z.string().max(500, "Farewell must be 500 characters or less"),
  voicePersona: z.enum(["professional", "friendly", "warm", "energetic", "calm"]),
  voiceGender: z.enum(["female", "male", "neutral"]),
  voiceSpeed: z.number().min(0.5).max(2.0),
  aiModel: z.enum(["llama3.1:8b", "llama3.1:70b", "mixtral:8x7b"]),
  maxCallDuration: z.number().min(60).max(3600),
  transferEnabled: z.boolean(),
  voicemailEnabled: z.boolean(),
  appointmentBookingEnabled: z.boolean(),
  messageTakingEnabled: z.boolean(),
  language: z.string(),
  customInstructions: z.string().max(2000).nullable(),
});

export const faqSchema = z.object({
  question: z.string().min(1, "Question is required").max(500),
  answer: z.string().min(1, "Answer is required").max(2000),
  category: z.string().max(50).nullable(),
  isActive: z.boolean(),
});

export type AiSettingsInput = z.infer<typeof aiSettingsSchema>;
export type FaqInput = z.infer<typeof faqSchema>;
