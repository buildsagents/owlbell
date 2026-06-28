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
      "Callers hear a natural, agency-trained receptionist voice — not a hold queue or voicemail tree. Behind that is AI tuned for plumbing intake: emergencies, service areas, pricing guardrails, and booking rules. Our US-based team writes and maintains your scripts; you are not configuring software on day one.",
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
      "Most shops are live within 48 hours of completing intake: Day 0 subscribe + form, Day 1 scripts and routing built by your specialist, Day 2 test calls and forward your main line. Rush onboarding is available if you already have clean service-area and pricing docs.",
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
      "Launch ($1,497/mo) has no separate setup fee — onboarding is included. Growth ($4,997/mo) includes a one-time $5,000 setup for calendar booking, CRM handoff, and dedicated success contact. Every fee is shown before you pay in Stripe checkout.",
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
      "Growth plans support handoff to Jobber, Housecall Pro, and other job-management tools your shop already uses. Launch focuses on capture, emergency routing, and owner SMS alerts. Tell us your stack during intake and we wire the workflow.",
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
      "Your script defines escalation: transfer to your on-call line, take a callback number, or schedule a follow-up. Most plumbing calls need fast intake, not small talk — but angry customers, insurance adjusters, or commercial accounts can be routed per your rules.",
  },
  {
    id: "emergency-flag",
    question: "How do emergency calls get flagged?",
    answer:
      "During onboarding we define emergency triggers with you — burst pipes, active leaks, no water, sewer backup, gas smell (refer to utility), etc. Flagged calls trigger immediate owner SMS with caller number, address, and issue summary.",
  },
  {
    id: "ai-disclosure",
    question: "Will callers know they are talking to AI?",
    answer:
      "Your call flow can include disclosure where required or where you prefer transparency. Many callers care more about fast help than the label. We optimize for clear, professional intake — not tricking anyone.",
  },
  {
    id: "phone-number",
    question: "What phone number do customers call?",
    answer:
      "Most shops forward their existing main line to Owlbell — customers keep calling the number on your truck. We can also provision a dedicated inbound number if you are splitting marketing lines or testing before switching the main line.",
  },
  {
    id: "keep-number",
    question: "Can I keep my existing business number?",
    answer:
      "Yes. Call forwarding from your carrier or VoIP provider is the usual setup. We walk you through forwarding codes during onboarding. Your public number stays the same; only the destination changes.",
  },
  {
    id: "pricing-after-trial",
    question: "How much does it cost after the trial?",
    answer:
      "Launch is $1,497/month. Growth is $4,997/month plus the one-time setup on that tier. The 7-day trial lets you validate call quality and workflow before the first monthly charge. Stripe sends receipts; cancel anytime from billing settings.",
  },
  {
    id: "service-area",
    question: "What areas do you serve?",
    answer:
      "US plumbing contractors only. We configure service areas, zip codes, and municipal boundaries during onboarding so out-of-area leads are politely declined or referred per your rules.",
  },
  {
    id: "learn-pricing",
    question: "How do you learn my pricing and services?",
    answer:
      "Intake form + a short kickoff call. You share service menu, trip charges, emergency premiums, and what you will not do (e.g., septic, commercial grease). We encode guardrails so the receptionist quotes within your bounds — never a competitor's price sheet.",
  },
  {
    id: "mistakes",
    question: "What if the AI gets something wrong?",
    answer:
      "Every call is logged with transcript and recording. You flag issues; our team adjusts scripts — included tuning for 30 days on Launch, ongoing on Growth. Plumbing has edge cases; we treat script updates as operations, not a ticket queue.",
  },
  {
    id: "spanish",
    question: "Do you support Spanish-speaking callers?",
    answer:
      "Bilingual intake can be configured on request during onboarding. Tell us your market mix — we will be direct about what is supported today and what is on the roadmap for your area.",
  },
  {
    id: "call-forwarding",
    question: "How do I forward my calls to Owlbell?",
    answer:
      "We send carrier-specific instructions (Verizon, AT&T, T-Mobile, RingCentral, etc.) after onboarding. Usually it is a simple unconditional forward code from your business cell or main line. Test calls confirm everything before you go live.",
  },
  {
    id: "trial-includes",
    question: "What is included in the 7-day trial?",
    answer:
      "Full answering on your forwarded line, owner SMS summaries, emergency routing, dashboard access, and script tuning by our team. You experience the same workflow paying customers get — not a neutered demo line.",
  },
  {
    id: "contract-term",
    question: "Is there a contract or minimum term?",
    answer:
      "Standard plans are month-to-month after trial. No annual lock-in required. Growth setup fee is one-time; monthly service can be cancelled with effect at the end of the current billing period.",
  },
];