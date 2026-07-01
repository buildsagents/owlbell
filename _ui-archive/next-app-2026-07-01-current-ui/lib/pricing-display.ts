export const PRICING_QUALIFIERS = [
  "Best for 40+ inbound calls/month",
  "Not for brand-new shops",
  "No long contract",
  "7-day test period",
  "Setup handled by Owlbell",
] as const;

export type PlanDisplay = {
  id: "basic" | "pro" | "pro_plus";
  name: string;
  payoff: string;
  rate: string;
  setupFee: string | null;
  blurb: string;
  features: string[];
  featured?: boolean;
};

export const PRIMARY_PLAN_DISPLAY: PlanDisplay[] = [
  {
    id: "basic",
    name: "Launch",
    payoff: "Pays for itself if it recovers 3-5 plumbing jobs/month.",
    rate: "£1,197/mo",
    setupFee: null,
    blurb: "Every call answered. Owner SMS alerts. Managed setup included.",
    features: [
      "24/7 answering + lead capture",
      "Emergency routing rules",
      "One number or call forwarding",
      "30-day script tuning",
    ],
  },
  {
    id: "pro",
    name: "Growth",
    payoff: "Pays for itself at ~10-12 booked jobs/month.",
    rate: "£3,997/mo",
    setupFee: "£4,000 one-time setup",
    blurb: "Booking workflow, CRM handoff, and a dedicated success contact.",
    featured: true,
    features: [
      "Everything in Launch",
      "Calendar booking + missed-call recovery",
      "CRM / job-management handoff",
      "Monthly revenue review",
    ],
  },
];

export const SCALE_PLAN_DISPLAY: PlanDisplay = {
  id: "pro_plus",
  name: "Scale",
  payoff: "For multi-location shops booking 25+ jobs/month from overflow.",
  rate: "£7,997+/mo",
  setupFee: "£8,000 one-time setup",
  blurb: "Multi-location, custom SLAs, dedicated success lead.",
  features: [],
};