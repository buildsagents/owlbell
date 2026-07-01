import { DEMO_AUDIO_SRC, PROOF_DISCLAIMER } from "@/lib/proof-data";

export { DEMO_AUDIO_SRC, PROOF_DISCLAIMER };

export type TranscriptLine = {
  role: "agent" | "caller";
  text: string;
};

/** Polished emergency intake preview used by the website demo. */
export const DEMO_TRANSCRIPT: TranscriptLine[] = [
  {
    role: "agent",
    text: "Thanks for calling Northstar Plumbing, this is Morgan. Are you calling about an emergency, or would you like to book a visit?",
  },
  {
    role: "caller",
    text: "It's an emergency. A pipe has burst under the sink and water is still coming through.",
  },
  {
    role: "agent",
    text: "I can help with that. If you can do it safely, turn off the stopcock. What name and address should I give the on-call plumber?",
  },
  {
    role: "caller",
    text: "Sarah Mitchell, 24 Maple Road, Bristol, BS6 5AL. We turned it off but there is still water on the floor.",
  },
  {
    role: "agent",
    text: "Thanks, Sarah. I have the address and I am marking this as active flooding. Is this the best number for the plumber to call back on?",
  },
  {
    role: "caller",
    text: "Yes, this number is fine. We're home all night if someone can come or call.",
  },
  {
    role: "agent",
    text: "I am alerting the on-call plumber now and holding an 8:30 AM follow-up if the emergency visit needs repair work. You will get a text confirmation in a moment.",
  },
  {
    role: "caller",
    text: "Okay, thank you. That's much better than leaving a voicemail.",
  },
  {
    role: "agent",
    text: "You're welcome. The on-call team has the details, and this number is on the job. Stay safe, Sarah.",
  },
];

export const DEMO_CALL_SUMMARY = {
  callerIssue: "Burst pipe under sink, active water after stopcock shutoff",
  urgency: "Emergency - active leak - occupant home",
  addressCaptured: "24 Maple Road, Bristol BS6 5AL",
  bookedSlot: "On-call escalation now - 8:30 AM follow-up held",
  ownerSms:
    "Emergency - burst pipe - Sarah M. - 24 Maple Road - active water - callback on file",
} as const;

export { CTA_DEMO_FLOW as DEMO_PAGE_CTA } from "@/lib/marketing-cta";
