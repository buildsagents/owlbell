import type { SeoLandingConfig } from "@/lib/seo-landing-pages";

export type CitySeoConfig = SeoLandingConfig & {
  city: string;
  state: string;
  slug: string;
};

function cityPage(
  slug: string,
  city: string,
  state: string,
  source: string,
  heroEm: string,
): CitySeoConfig {
  const path = `/plumbers-in-${slug}`;
  return {
    slug,
    city,
    state,
    path,
    source,
    metadata: {
      title: `AI Answering Service for Plumbers in ${city} - 24/7 Emergency Intake | Owlbell`,
      description: `Managed AI receptionist for ${city}, ${state} plumbing shops. After-hours emergency calls answered, jobs booked, owner SMS - we set it up, you forward missed calls.`,
    },
    hero: {
      kicker: `${city} plumbing - Managed setup`,
      headline: `After-hours plumbing calls in ${city}`,
      headlineEm: heroEm,
      lead: `${city} emergencies don't wait for business hours. Owlbell answers overflow and after-hours calls for ${city} plumbing shops - qualifies burst pipes and sewer backups, books slots, texts your crew.`,
    },
    timeline: [
      { time: "10:52 PM", event: `Inbound - ${city} burst pipe call` },
      { time: "10:52 PM", event: "Answered 1.8s - emergency flagged" },
      { time: "10:54 PM", event: "Address + service area confirmed" },
      { time: "10:54 PM", event: "Owner SMS - morning slot booked" },
    ],
    sections: [
      {
        id: "local-fit",
        kicker: `${city} metro`,
        title: `Built for ${city} plumbing demand patterns`,
        paragraphs: [
          `${city}-area shops see the same leak: ads and LSAs drive rings, but after-hours and on-job overflow still hits voicemail. Homeowners call the next listing within minutes.`,
          `Owlbell configures your service area, zip boundaries, trip charges, and emergency matrix for ${city} - not generic national scripts.`,
          `Start with a free missed-call audit. We send a recovery report and sample script before any voice setup or billing.`,
        ],
        stats: [
          { label: "Typical miss rate", value: "8-15 / wk" },
          { label: "Emergency job", value: "£350-£900" },
          { label: "Avg pickup", value: "1.8s" },
        ],
      },
      {
        id: "coverage",
        kicker: "After hours",
        title: "Nights, weekends, and holiday overflow",
        warm: true,
        paragraphs: [
          `Many ${city} shops keep daytime office staff and forward after-hours overflow to Owlbell. We answer simultaneous rings during Monday morning rush too.`,
        ],
        bullets: [
          "Burst pipe - sewer backup - water heater - drain clog",
          "Owner SMS with caller, issue, address, booked slot",
          "Jobber / ServiceTitan / Housecall Pro on Growth",
          "7-day call capture test after audit",
        ],
      },
    ],
  };
}

export const CITY_SEO_PAGES: Record<string, CitySeoConfig> = {
  austin: cityPage("austin", "Austin", "TX", "city_austin", " should not go to voicemail."),
  phoenix: cityPage("phoenix", "Phoenix", "AZ", "city_phoenix", " need a clear booking path."),
  denver: cityPage("denver", "Denver", "CO", "city_denver", " can't wait until Monday."),
  dallas: cityPage("dallas", "Dallas", "TX", "city_dallas", " are high-intent and urgent."),
  houston: cityPage("houston", "Houston", "TX", "city_houston", " spike after storms."),
};

export const NICHE_SEO_PAGE: SeoLandingConfig = {
  path: "/best-emergency-plumbing-answering",
  source: "niche_emergency",
  metadata: {
    title: "Best Answering Service for Emergency Plumbers - Managed AI | Owlbell",
    description:
      "Best fit for emergency plumbing shops that advertise 24/7 service: managed AI intake, triage, booking, and owner SMS - not generic message-taking.",
  },
  hero: {
    kicker: "Emergency plumbing - Managed AI",
    headline: "Best answering service",
    headlineEm: " for emergency plumbers who book jobs.",
    lead:
      "Generic call centers take messages. Owlbell qualifies emergencies, captures addresses, books dispatch slots, and texts owners - trade-tuned scripts configured for your shop.",
  },
  timeline: [
    { time: "11:04 PM", event: "Burst pipe - basement flooding" },
    { time: "11:04 PM", event: "Emergency tier - main valve off" },
    { time: "11:06 PM", event: "On-call alert + AM slot booked" },
    { time: "11:06 PM", event: "Owner SMS before competitor callback" },
  ],
  sections: [
    {
      id: "why-not-generic",
      kicker: "Emergency-first",
      title: "Message-taking is not emergency plumbing intake",
      paragraphs: [
        "Emergency plumbers need shutoff status, active flow, occupant home, zip in service area, and after-hours fee disclosure - not a name and number for tomorrow's callback.",
        "Owlbell runs plumbing triage scripts, flags true emergencies, and books when appropriate. Every call recorded for your review.",
      ],
      bullets: [
        "Burst pipe / sewer / slab leak - emergency matrix",
        "24/7 pickup with under-2-second answer",
        "Owner SMS on every booked job",
        "Free audit before 7-day capture test",
      ],
    },
    {
      id: "ladder",
      kicker: "Offer ladder",
      title: "Audit first - then prove it on your line",
      warm: true,
      paragraphs: [
        "Free missed-call audit -> 7-day call capture test -> Launch £1,197/mo -> Growth £3,997/mo with calendar + CRM handoff.",
        "Managed setup throughout - you forward missed calls, we configure and tune scripts.",
      ],
      stats: [
        { label: "Launch breakeven", value: "3-5 jobs/mo" },
        { label: "Trial", value: "7 days" },
        { label: "Contract", value: "Month-to-month" },
      ],
    },
  ],
};

export function getCitySeoConfig(slug: string): CitySeoConfig | undefined {
  return CITY_SEO_PAGES[slug];
}

export function getAllCitySlugs(): string[] {
  return Object.keys(CITY_SEO_PAGES);
}