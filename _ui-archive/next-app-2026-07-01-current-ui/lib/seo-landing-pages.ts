export type SeoStat = {
  label: string;
  value: string;
};

export type SeoSection = {
  id: string;
  kicker: string;
  title: string;
  intro?: string;
  paragraphs: string[];
  warm?: boolean;
  stats?: SeoStat[];
  bullets?: string[];
};

export type SeoLandingConfig = {
  path: string;
  source: string;
  metadata: {
    title: string;
    description: string;
  };
  hero: {
    kicker: string;
    headline: string;
    headlineEm?: string;
    lead: string;
  };
  sections: SeoSection[];
  timeline?: { time: string; event: string }[];
};

const SITE_URL = "https://owlbell.xyz";

export function seoPageUrl(path: string): string {
  return `${SITE_URL}${path}`;
}

export const SEO_LANDING_PAGES: Record<string, SeoLandingConfig> = {
  "missed-plumbing-calls": {
    path: "/missed-plumbing-calls",
    source: "missed_calls",
    metadata: {
      title: "Missed Plumbing Calls - Cost, Recovery & 24/7 Answering | Owlbell",
      description:
        "How many plumbing calls does your shop miss per week? See the revenue at risk, why voicemail loses emergencies, and how managed AI answering recovers booked jobs by SMS.",
    },
    hero: {
      kicker: "Missed call recovery - Managed setup",
      headline: "Every missed plumbing call",
      headlineEm: " is a job your competitor books.",
      lead:
        "Homeowners hang up in seconds when nobody answers. Owlbell picks up overflow and after-hours calls, qualifies emergencies, and texts your team before they dial the next plumber.",
    },
    timeline: [
      { time: "7:12 PM", event: "Inbound call - no answer, no voicemail left" },
      { time: "7:13 PM", event: "Homeowner calls next listing on Google" },
      { time: "7:18 PM", event: "Competitor books £420 drain job" },
      { time: "Next AM", event: "Your office never knew the call happened" },
    ],
    sections: [
      {
        id: "hidden-cost",
        kicker: "The hidden leak",
        title: "Most missed calls never leave a voicemail",
        intro:
          "You only count the messages you get back. The expensive ones are the hang-ups.",
        paragraphs: [
          "Plumbing demand is urgent. When a pipe bursts at 10 PM, the caller dials three companies in five minutes. If your line rings out, that revenue is gone - often without a trace in your phone log.",
          "Shops running Google Ads or Local Services Ads pay for every click that becomes a ring. Letting those rings hit voicemail is one of the highest-cost leaks in the trade.",
          "Owlbell answers every overflow and after-hours call in under two seconds, captures address and issue, flags emergencies, and sends an owner SMS with booked slot and estimated job value.",
        ],
        stats: [
          { label: "Typical miss rate", value: "8-15 / wk" },
          { label: "Avg booked job", value: "£350-£600" },
          { label: "Monthly at risk", value: "£5.6k-£36k" },
        ],
      },
      {
        id: "recovery",
        kicker: "Recovery workflow",
        title: "From missed ring to booked job by SMS",
        warm: true,
        paragraphs: [
          "Forward your main line or after-hours overflow to Owlbell. We configure scripts for burst pipes, sewer backups, water heaters, and routine service - your hours, your service area, your emergency rules.",
          "You do not configure voice or CRM upfront. Start with a free missed-call audit - we model your shop's numbers and send a sample script before you commit.",
        ],
        bullets: [
          "24/7 pickup - nights, weekends, lunch rush",
          "Emergency triage with your fee disclosure",
          "Owner SMS: caller, issue, address, time slot",
          "Recordings and transcripts in your dashboard",
        ],
      },
    ],
  },

  "after-hours-plumbing-answering": {
    path: "/after-hours-plumbing-answering",
    source: "after_hours",
    metadata: {
      title: "After-Hours Plumbing Answering - 24/7 Emergency Intake | Owlbell",
      description:
        "Answer plumbing emergencies after hours without hiring night staff. Managed AI receptionist for burst pipes, sewer backups, and no-hot-water calls - owner SMS on every booked job.",
    },
    hero: {
      kicker: "24/7 plumbing intake - We set it up",
      headline: "After-hours plumbing calls",
      headlineEm: " should not go to voicemail.",
      lead:
        "Emergencies spike between 6 PM and midnight - when your crew is off the clock. Owlbell answers, qualifies, books, and texts your on-call team the details.",
    },
    timeline: [
      { time: "10:47 PM", event: "Burst pipe - basement flooding" },
      { time: "10:47 PM", event: "Answered 1.8s - emergency flagged" },
      { time: "10:49 PM", event: "Address + ZIP captured" },
      { time: "10:49 PM", event: "Owner SMS - AM slot booked" },
    ],
    sections: [
      {
        id: "when-calls-hit",
        kicker: "When calls actually hit",
        title: "Plumbing emergencies do not wait for Monday",
        paragraphs: [
          "Burst pipes, sewage backups, and no-hot-water calls cluster after dinner and on weekends - exactly when office staff are home and your main line forwards to voicemail.",
          "A generic answering service takes a message. Owlbell runs plumbing intake: shutoff status, active flow, rental vs. owner, service area check, after-hours fee disclosure, and true emergency escalation to your on-call tech.",
          "One booked after-hours emergency often covers a month of service at typical ticket sizes. Speed-to-answer matters because water damage compounds hourly.",
        ],
      },
      {
        id: "coverage",
        kicker: "Coverage model",
        title: "Nights, weekends, and holiday overflow",
        warm: true,
        paragraphs: [
          "Many shops keep daytime office staff and use Owlbell for after-hours and simultaneous rings during Monday morning rush. One person can only talk to one homeowner at a time - AI handles the long tail.",
          "We configure your emergency matrix: burst pipe -> immediate owner text, drain clog -> next-morning window, gas smell -> escalate to 911 script. Your rules, not generic defaults.",
        ],
        bullets: [
          "24/7/365 - no holiday gaps",
          "On-call SMS with map-ready address",
          "Calendar booking on Growth plans",
          "Managed setup - forward missed calls, we tune scripts",
        ],
      },
    ],
  },

  "plumbing-answering-service-vs-ai": {
    path: "/plumbing-answering-service-vs-ai",
    source: "vs_answering",
    metadata: {
      title: "Plumbing Answering Service vs AI - Compare Options | Owlbell",
      description:
        "Generic answering service vs DIY AI vs Owlbell managed receptionist for plumbers. Compare cost per booked job, not cost per minute.",
    },
    hero: {
      kicker: "Comparison - Cost per booked job",
      headline: "Plumbing answering service",
      headlineEm: " vs managed AI receptionist",
      lead:
        "National call centers take messages. Owlbell qualifies plumbing jobs, applies your guardrails, books slots, and texts your team - trade-tuned scripts configured for you.",
    },
    sections: [
      {
        id: "compare",
        kicker: "Three options",
        title: "Message-taking vs booking workflow",
        paragraphs: [
          "Price alone misleads. A £300/month answering service that never books into your calendar costs more than managed answering that converts calls into dispatch events.",
        ],
        bullets: [
          "Generic answering (£200-£800/mo): per-minute fees, shared agent pool, message-taking, lost emergency nuance",
          "DIY AI bot (low software + high owner time): unfinished setup, broken holiday weekends, no plumbing defaults",
          "Owlbell managed (£1,197+/mo): we configure scripts, 24/7 pickup, owner SMS, dashboard recordings, script tuning from real calls",
        ],
      },
      {
        id: "booked-job",
        kicker: "The right metric",
        title: "Measure cost per booked job - not cost per minute",
        warm: true,
        paragraphs: [
          "Ask how many after-hours emergencies your answering service actually books on your calendar. If the answer is \"they take a message,\" you are paying for half a solution.",
          "Owlbell Launch pays for itself at 3-5 recovered plumbing jobs per month. Growth adds Jobber, ServiceTitan, and Housecall Pro handoff plus calendar booking.",
          "Hear a real burst-pipe intake on our demo page - same Retell flow we deploy after managed setup.",
        ],
        stats: [
          { label: "Owlbell avg pickup", value: "1.8s" },
          { label: "Voicemail after go-live", value: "0/wk" },
          { label: "Trial period", value: "7 days" },
        ],
      },
    ],
  },

  "ai-receptionist-for-plumbers": {
    path: "/ai-receptionist-for-plumbers",
    source: "ai_receptionist",
    metadata: {
      title: "AI Receptionist for Plumbers - Managed 24/7 Answering | Owlbell",
      description:
        "Managed AI receptionist built for UK plumbing contractors. We configure voice and scripts; you forward missed calls; emergencies get booked and texted to your team.",
    },
    hero: {
      kicker: "Managed AI receptionist - Plumbing only",
      headline: "AI receptionist for plumbers",
      headlineEm: " that books jobs - not just takes messages.",
      lead:
        "Owlbell is a product service for established plumbing shops - not a DIY bot builder. We set up voice, emergency routing, and owner SMS. You forward missed calls.",
    },
    timeline: [
      { time: "9:18 PM", event: "Sewer backup - main line clogged" },
      { time: "9:18 PM", event: "Emergency tier confirmed" },
      { time: "9:20 PM", event: "On-call alert + callback captured" },
      { time: "9:20 PM", event: "Owner SMS with address + est. value" },
    ],
    sections: [
      {
        id: "what-it-does",
        kicker: "What it does",
        title: "Front door for legitimate plumbing demand",
        paragraphs: [
          "An AI receptionist for plumbers handles the calls your office cannot: after-hours overflow, simultaneous rings, and lunch-hour gaps. It is not a replacement for 911 or gas-line emergencies you script to escalate immediately.",
          "Callers hear a natural receptionist trained on your shop - services, service area, trip charges, and emergency rules. Behind it: structured capture, booking when appropriate, and SMS summaries with estimated job value.",
        ],
        bullets: [
          "Burst pipe, sewer, water heater, drain - tuned defaults",
          "Service area and zip boundaries per your shop",
          "Recordings + transcripts for dispute resolution",
          "Jobber / ServiceTitan / Housecall Pro on Growth",
        ],
      },
      {
        id: "who-fits",
        kicker: "Who it fits",
        title: "Built for shops that cannot miss high-value calls",
        warm: true,
        paragraphs: [
          "Best fit: 40+ inbound calls per month, average job above £300, real after-hours emergency mix, active Google Ads or LSA spend.",
          "Poor fit: brand-new one-truck operators still building demand, or shops optimizing for cheapest per-minute rate without booking workflow. We say that plainly.",
          "Start with a free missed-call audit - two minutes, no voice setup or billing required upfront.",
        ],
      },
    ],
  },

  "emergency-plumbing-call-answering": {
    path: "/emergency-plumbing-call-answering",
    source: "emergency",
    metadata: {
      title: "Emergency Plumbing Call Answering - 24/7 Triage & Dispatch | Owlbell",
      description:
        "Answer emergency plumbing calls 24/7: burst pipes, active leaks, sewer backups. Managed intake, on-call SMS, and booked dispatch slots - configured for your shop.",
    },
    hero: {
      kicker: "Emergency intake - Managed setup",
      headline: "Emergency plumbing calls",
      headlineEm: " answered in under two seconds.",
      lead:
        "Burst pipe at 11 PM. Owlbell classifies urgency, captures address, alerts the on-call team, and texts the owner before the homeowner calls the next listing.",
    },
    timeline: [
      { time: "11:04 PM", event: "Burst pipe - basement flooding" },
      { time: "11:04 PM", event: "Emergency flagged - occupant home" },
      { time: "11:06 PM", event: "Address and callback captured" },
      { time: "11:06 PM", event: "On-call routed - owner SMS sent" },
    ],
    sections: [
      {
        id: "triage",
        kicker: "Emergency triage",
        title: "Scripts tuned for real plumbing emergencies",
        paragraphs: [
          "Generic bots ask \"How can I help?\" Owlbell asks the questions dispatchers need: Is water actively flowing? Main shutoff status? Occupants home? Rental or owner? Zip in service area?",
          "True emergencies escalate per your matrix - burst pipe with standing water gets owner text and on-call routing. Routine drain clogs get next-available booking without waking your whole crew.",
          "Every emergency call is recorded. You review how triage ran and we tune wording from flagged calls during setup.",
        ],
        stats: [
          { label: "Sample emergency job", value: "~£850" },
          { label: "Avg answer time", value: "1.8s" },
          { label: "Coverage", value: "24/7/365" },
        ],
      },
      {
        id: "scenarios",
        kicker: "Common scenarios",
        title: "What we configure on day one",
        warm: true,
        paragraphs: [
          "Your emergency matrix is shop-specific - trip charges, after-hours fees, and which issues wake the on-call tech vs. book for morning.",
        ],
        bullets: [
          "Burst pipe - basement flooding - emergency + AM dispatch",
          "Sewer backup - main line - on-call alert",
          "Water heater - no hot water - urgent same-day or next AM",
          "Slab leak - active moisture - escalate + callback capture",
        ],
      },
    ],
  },

  "plumbing-call-audit": {
    path: "/plumbing-call-audit",
    source: "call_audit",
    metadata: {
      title: "Free Plumbing Call Audit - Missed-Call Recovery Report | Owlbell",
      description:
        "Free missed-call recovery audit for plumbing shops. Tell us your volume and service area - we send a custom report and sample script. No setup or billing required.",
    },
    hero: {
      kicker: "Free audit - 2 minutes - No commitment",
      headline: "Free plumbing call audit",
      headlineEm: " for your shop.",
      lead:
        "Tell us your business name, service area, and how many calls you miss per week. We send a missed-call recovery audit and sample script - no voice config, CRM, or billing upfront.",
    },
    sections: [
      {
        id: "what-you-get",
        kicker: "What you receive",
        title: "Missed-call recovery audit + sample script",
        paragraphs: [
          "Within one business day you get a plain-language report: estimated revenue at risk from missed after-hours calls, how your current flow compares to shops using managed answering, and a sample intake script tuned for plumbing emergencies.",
          "No 7-step wizard. No Stripe checkout before you see value. If the numbers make sense, we configure Owlbell on your line during a 7-day trial - you forward missed calls, we tune from real conversations.",
        ],
        bullets: [
          "Business name, website, service area, main phone",
          "Missed calls per week + emergency coverage (yes/no)",
          "Best email for your audit delivery",
          "Managed setup handled by Owlbell after you approve",
        ],
      },
      {
        id: "why-audit",
        kicker: "Why start here",
        title: "See your numbers before you commit",
        warm: true,
        paragraphs: [
          "Plumbing owners open audit links from email on their phone between jobs. The form is short on purpose - two minutes, mobile-friendly, saves locally if you need to finish later.",
          "Use our ROI calculator on the homepage to rough your monthly exposure, then submit the audit for a shop-specific read. Hear a real burst-pipe recording on the demo page while you wait.",
        ],
        stats: [
          { label: "Form time", value: "~2 min" },
          { label: "Audit delivery", value: "1 biz day" },
          { label: "Trial after signup", value: "7 days" },
        ],
      },
    ],
  },
};

export function getSeoLandingConfig(slug: keyof typeof SEO_LANDING_PAGES): SeoLandingConfig {
  return SEO_LANDING_PAGES[slug];
}

export function buildSeoJsonLd(config: SeoLandingConfig) {
  const url = seoPageUrl(config.path);
  return {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebPage",
        "@id": `${url}#webpage`,
        url,
        name: config.metadata.title,
        description: config.metadata.description,
        isPartOf: { "@id": `${SITE_URL}/#website` },
        inLanguage: "en-GB",
      },
      {
        "@type": "Service",
        name: "Owlbell AI Receptionist for Plumbers",
        serviceType: "Plumbing call answering and emergency intake",
        provider: {
          "@type": "Organization",
          name: "Owlbell",
          url: SITE_URL,
          email: "hello@owlbell.xyz",
        },
        areaServed: { "@type": "Country", name: "United Kingdom" },
        description: config.metadata.description,
      },
    ],
  };
}
