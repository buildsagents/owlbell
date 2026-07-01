export type FaqItem = {
  id: string;
  question: string;
  answer: string;
};

/** Primary fear-reduction questions - surfaced on FAQ, About, and homepage */
export const TRUST_FAQ_IDS = [
  "real-company",
  "who-sets-up",
  "ai-mistakes",
  "callers-know-ai",
  "recording-legal",
  "crm-integrations",
  "after-hours",
  "cancel",
] as const;

export const FAQ_ITEMS: FaqItem[] = [
  {
    id: "real-company",
    question: "Is this a real company?",
    answer:
      "Yes. Owlbell is a UK-based managed reception agency built for plumbing shops - not an offshore call center or a faceless lead form. We publish pricing on the site, offer a free missed-call audit before you commit, and reply from hello@owlbell.xyz on UK business days. Privacy Policy and Terms are linked in the footer. You can hear a real sample call and review anonymized results before signing up.",
  },
  {
    id: "who-sets-up",
    question: "Who sets this up?",
    answer:
      "We do - not you. You fill out a short audit form (business name, service area, phone, missed-call volume). Our team configures voice, emergency scripts, hours, forwarding, and integrations. You forward missed calls to Owlbell. We tune the script from real conversations during your trial. No DIY bot builder, no API keys, no weekend spent in settings.",
  },
  {
    id: "ai-mistakes",
    question: "What if the AI gets it wrong?",
    answer:
      "Every call is recorded and transcribed in your dashboard. You get an owner SMS with caller, issue, address, and booked slot - so you can catch gaps fast. Scripts include escalation rules: transfer to on-call, capture a callback, or flag for human follow-up when the AI is unsure. We refine wording from flagged calls during setup and ongoing tuning. The AI does not quote prices or promise work outside your guardrails.",
  },
  {
    id: "callers-know-ai",
    question: "Can callers tell it is AI?",
    answer:
      "Most callers care that someone competent answers in under two seconds - not whether it is human. The voice is natural and introduces itself as your shop's receptionist. We configure disclosure per your preference. UK call flows include recording disclosure where required under PECR.",
  },
  {
    id: "recording-legal",
    question: "Is call recording legal?",
    answer:
      "Yes, when done correctly - and we help you do that. Owlbell records calls for quality, dispute resolution, and your review. UK inbound calls use disclosure language aligned with PECR. Outbound campaigns follow CTPS and your opt-in rules. Recordings and transcripts live in your dashboard. See our Privacy Policy for retention and access details.",
  },
  {
    id: "crm-integrations",
    question: "Does this work with Jobber, ServiceTitan, or Housecall Pro?",
    answer:
      "Yes - on Growth plans. We hand off booked jobs via calendar sync, CRM notes, or structured SMS/email summaries your dispatcher can paste into Jobber, ServiceTitan, Housecall Pro, or similar tools. Launch covers 24/7 capture, emergency routing, and owner SMS alerts. Tell us your stack during the audit; we configure handoff during managed setup.",
  },
  {
    id: "after-hours",
    question: "What happens after hours?",
    answer:
      "Owlbell answers 24/7/365 - nights, weekends, and holidays included. After-hours emergency calls follow your rules: burst pipe -> owner text + booked slot, sewage backup -> escalate, routine drain -> next-morning window. You wake up to SMS summaries instead of voicemail callbacks. Most plumbing revenue is lost between 6 PM and 8 AM; that is when Owlbell pays for itself.",
  },
  {
    id: "cancel",
    question: "Can I cancel?",
    answer:
      "Yes. Every plan includes a 7-day trial - cancel before day seven and you are not charged the monthly fee. After trial, plans are month-to-month with no long-term contract. Email hello@owlbell.xyz or use your billing portal. Setup fees on Growth, if applicable, are disclosed before you pay. We would rather earn your business from booked jobs than lock you in.",
  },
  {
    id: "go-live-speed",
    question: "How fast can we go live?",
    answer:
      "Most shops are live within a few business days after the audit. You share services, hours, and emergency rules - we configure voice, scripts, and forwarding. Once you forward missed calls, we tune from real conversations and you start getting booked jobs by SMS.",
  },
  {
    id: "existing-answering",
    question: "We already use an answering service - why switch?",
    answer:
      "Traditional services take messages. Owlbell qualifies the job, applies your pricing guardrails, books on your calendar when appropriate, and texts you a structured summary with estimated job value. You get fewer callbacks and more booked work from the same ad spend.",
  },
  {
    id: "setup-fee",
    question: "Is there a setup fee?",
    answer:
      "Launch (£1,197/mo) includes managed setup - we configure voice, scripts, and routing for you. Growth (£3,997/mo) adds a one-time £4,000 setup for calendar booking, CRM handoff, and a dedicated success contact. Every fee is shown before you pay.",
  },
  {
    id: "caller-data",
    question: "Who owns the caller data?",
    answer:
      "You do. Owlbell processes caller information on your behalf as a service provider. Data is used to answer calls, book jobs, and notify your team - not sold to third parties. Export and deletion requests are handled per our Privacy Policy.",
  },
  {
    id: "calendar-booking",
    question: "Can Owlbell book appointments on my calendar?",
    answer:
      "On Growth, yes - with your availability rules, drive-time buffers, and double-book prevention. Launch captures lead details and flags emergencies; booking can be added when you upgrade.",
  },
  {
    id: "human-escalation",
    question: "What if a caller needs to talk to a human?",
    answer:
      "Your script defines escalation: transfer to your on-call plumber, take a callback number, or schedule a follow-up. Angry customers, insurance adjusters, or commercial accounts can be routed per your rules.",
  },
  {
    id: "tcpa-gdpr",
    question: "How do you handle UK compliance (PECR, GDPR, CTPS)?",
    answer:
      "Inbound: recording disclosure in your greeting, secure storage, and GDPR-ready export/deletion per our Privacy Policy. Outbound sales campaigns use CTPS screening and documented opt-in where required. We do not run founder cold calls - async email and managed voice agents only.",
  },
];

export const TRUST_FAQ_ITEMS = FAQ_ITEMS.filter((item) =>
  TRUST_FAQ_IDS.includes(item.id as (typeof TRUST_FAQ_IDS)[number]),
);