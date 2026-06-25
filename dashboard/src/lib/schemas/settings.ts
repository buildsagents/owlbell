import { z } from "zod";
import type { IntegrationProvider } from "@/types/integration";

export const WeekdaySchema = z.union([
  z.literal(0), z.literal(1), z.literal(2), z.literal(3),
  z.literal(4), z.literal(5), z.literal(6),
]);

export const BusinessHoursSchema = z.object({
  dayOfWeek: WeekdaySchema,
  isOpen: z.boolean(),
  openTime: z.string().regex(/^\d{2}:\d{2}$/, "Must be in HH:mm format"),
  closeTime: z.string().regex(/^\d{2}:\d{2}$/, "Must be in HH:mm format"),
  is24Hours: z.boolean(),
  breaks: z.array(z.object({
    start: z.string().regex(/^\d{2}:\d{2}$/),
    end: z.string().regex(/^\d{2}:\d{2}$/),
  })).optional(),
});

export type BusinessHours = z.infer<typeof BusinessHoursSchema>;

export const NotificationPreferencesSchema = z.object({
  emailEnabled: z.boolean(),
  pushEnabled: z.boolean(),
  smsEnabled: z.boolean().optional(),
  slackEnabled: z.boolean().optional(),
  callCompleted: z.boolean(),
  callMissed: z.boolean(),
  messageReceived: z.boolean(),
  appointmentBooked: z.boolean(),
  usageWarning: z.boolean(),
  teamInvite: z.boolean(),
  quietHoursEnabled: z.boolean(),
  quietHoursStart: z.string().nullable(),
  quietHoursEnd: z.string().nullable(),
});

export type NotificationPreferences = z.infer<typeof NotificationPreferencesSchema>;

export const FaqCategorySchema = z.enum([
  "general", "billing", "support", "product", "other",
]);

export const KnowledgeBaseEntrySchema = z.object({
  question: z.string().min(1, "Question is required").max(500),
  answer: z.string().min(1, "Answer is required").max(5000),
  category: FaqCategorySchema.nullable(),
  tags: z.array(z.string().max(50)).optional(),
  isActive: z.boolean().optional(),
});

export type KnowledgeBaseEntry = z.infer<typeof KnowledgeBaseEntrySchema>;

const integrationProviders = [
  "google_calendar", "outlook_calendar", "slack", "hubspot",
  "salesforce", "zapier", "webhook", "twilio", "sendgrid", "mailchimp",
] as const;

export const IntegrationConfigSchema = z.object({
  provider: z.enum(integrationProviders),
  apiKey: z.string().optional(),
  webhookUrl: z.string().url("Must be a valid URL").optional().or(z.literal("")),
  enabled: z.boolean(),
  config: z.record(z.string(), z.unknown()).optional(),
});

export type IntegrationConfig = z.infer<typeof IntegrationConfigSchema>;

export const VoiceTypeSchema = z.enum(["professional", "friendly", "warm", "energetic", "calm"]);

export const GreetingStyleSchema = z.enum(["formal", "casual", "friendly", "professional"]);

export const AIPersonalitySchema = z.object({
  voiceType: VoiceTypeSchema,
  greetingStyle: GreetingStyleSchema,
  formalityLevel: z.number().int().min(1).max(5),
  customInstructions: z.string().max(2000).nullable(),
});

export type AIPersonality = z.infer<typeof AIPersonalitySchema>;

export const IntegrationProviderSchema = z.enum(integrationProviders);
export type { IntegrationProvider };
