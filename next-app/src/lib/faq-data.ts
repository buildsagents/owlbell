export type FaqItem = {
  id: string;
  question: string;
  answer: string;
};

export const FAQ_ITEMS: FaqItem[] = [
  {
    id: "real-person",
    question: "Is a real person answering my calls?",
    answer:
      "Callers hear a natural AI receptionist voice tuned for your trade — not hold music or voicemail. You configure greeting, scripts, and routing in self-serve onboarding. Chat and email support are available if you want a human to review your setup.",
  },
  {
    id: "recording-legal",
    question: "Are call recordings legal?",
    answer:
      "Owlbell records calls for quality, dispute resolution, and your review. Many states require one- or two-party consent. We include disclosure language in your call flow and help you align with your state's rules. You can access recordings from your dashboard. See our Privacy Policy for retention details.",
  },
  {
    id: "servicetitan",
    question: "Does Owlbell work with ServiceTitan?",
    answer:
      "Yes — on Growth plans we hand off booked jobs to ServiceTitan (and similar platforms) via your preferred workflow: calendar sync, CRM notes, or structured SMS/email summaries your dispatcher can paste in. Launch covers capture and owner alerts; Growth adds deeper job-management integration.",
  },
  {
    id: "go-live-speed",
    question: "How fast can we go live?",
    answer:
      "Self-serve onboarding targets under 15 minutes from signup to first test call. You configure voice, scripts, hours, calendar, and forwarding in the wizard; activation provisions your line immediately (Retell when configured, or your forward number in sandbox). Human support is available same-day if you need help.",
  },
  {
    id: "trial-cancel",
    question: "Can I cancel during the 7-day trial?",
    answer:
      "Yes. Cancel before day seven and you are not charged the monthly plan fee. Setup fees on Growth, if applicable, are disclosed at checkout. No long-term lock-in on standard plans — month-to-month after trial.",
  },
  {
    id: "setup-fee",
    question: "Is there a setup fee?",
    answer:
      "Launch ($1,497/mo) has no separate setup fee — self-serve onboarding is included. Growth ($4,997/mo) includes a one-time $5,000 setup for calendar booking, CRM handoff, and dedicated success contact. Every fee is shown before you pay in Stripe checkout.",
  },
  {
    id: "after-hours",
    question: "What about after-hours, weekends, and holidays?",
    answer:
      "Owlbell answers 24/7/365. Nights, Sundays, and lunch rush are when most plumbing emergencies hit — and when voicemail loses the most revenue. Emergency calls follow your rules (e.g., burst pipe → immediate owner text + next-morning slot).",
  },
  {
    id: "existing-answering",
    question: "We already use an answering service — why switch?",
    answer:
      "Traditional services take messages. Owlbell qualifies the job, applies your pricing guardrails, books on your calendar when appropriate, and texts you a structured summary with estimated job value. You get fewer callbacks and more booked work from the same ad spend.",
  },
  {
    id: "jobber-housecall",
    question: "Do you integrate with Jobber or Housecall Pro?",
    answer:
      "Growth plans support handoff to Jobber, Housecall Pro, and other job-management tools your shop already uses. Launch focuses on capture, emergency routing, and owner SMS alerts. Select your stack during onboarding.",
  },
  {
    id: "caller-data",
    question: "Who owns the caller data?",
    answer:
      "You do. Owlbell processes caller information on your behalf as a service provider. Data is used to answer calls, book jobs, and notify your team — not sold to third parties. Export and deletion requests are handled per our Privacy Policy and DPA.",
  },
  {
    id: "calendar-booking",
    question: "Can Owlbell book appointments on my calendar?",
    answer:
      "On Growth, yes — with your availability rules, drive-time buffers, and double-book prevention. Launch captures lead details and flags emergencies; booking can be added when you upgrade or during onboarding if you start on Growth.",
  },
  {
    id: "human-escalation",
    question: "What if a caller needs to talk to a human?",
    answer:
      "Your script defines escalation: transfer to your on-call line, take a callback number, or schedule a follow-up. Most service calls need fast intake, not small talk — but angry customers, insurance adjusters, or commercial accounts can be routed per your rules.",
  },
  {
    id: "multi-device",
    question: "Can I pause onboarding and finish on my phone?",
    answer:
      "Yes. Progress saves locally and to the cloud. Use the resume link shown in onboarding (?draft_id=…) or sign in with the same email on another device to pick up where you left off.",
  },
  {
    id: "tcpa-gdpr",
    question: "How do you handle TCPA and GDPR?",
    answer:
      "We include recording disclosures in your greeting, support opt-out language where required, and encrypt stored transcripts. GDPR-ready data handling and export/deletion are documented in our Privacy Policy.",
  },
];