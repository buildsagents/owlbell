export type VerticalSlug =
  | "plumbing"
  | "hvac"
  | "electrical"
  | "dental"
  | "legal";

export type VerticalConfig = {
  slug: VerticalSlug;
  path: string;
  trade: string;
  headline: string;
  subhead: string;
  painPoints: string[];
  sampleServices: string;
  defaultGreeting: string;
};

export const VERTICALS: VerticalConfig[] = [
  {
    slug: "plumbing",
    path: "/plumbing-ai-receptionist",
    trade: "Plumbing",
    headline: "Every plumbing emergency answered — you get the text.",
    subhead: "24/7 AI receptionist built for US plumbing contractors.",
    painPoints: ["Burst pipes after hours", "Voicemail during peak season", "Slow callback on estimates"],
    sampleServices: "Leak repair, drain cleaning, water heaters, sewer line, emergency plumbing",
    defaultGreeting: "Thanks for calling — how can we help with your plumbing today?",
  },
  {
    slug: "hvac",
    path: "/hvac-ai-receptionist",
    trade: "HVAC",
    headline: "No AC outage goes to voicemail.",
    subhead: "Book service calls and flag no-heat emergencies automatically.",
    painPoints: ["Summer heat-wave call spikes", "After-hours no-heat calls", "Missed maintenance upsells"],
    sampleServices: "AC repair, furnace service, tune-ups, duct cleaning, emergency HVAC",
    defaultGreeting: "Thanks for calling — are you calling about heating, cooling, or maintenance?",
  },
  {
    slug: "electrical",
    path: "/electrical-ai-receptionist",
    trade: "Electrical",
    headline: "Spark safety issues to your crew instantly.",
    subhead: "Qualify urgent electrical calls and schedule estimates 24/7.",
    painPoints: ["Safety-critical after-hours calls", "Panel upgrade leads lost", "Dispatcher overload"],
    sampleServices: "Panel upgrades, outlet repair, EV charger install, emergency electrician",
    defaultGreeting: "Thanks for calling — tell me what's going on with your electrical issue.",
  },
  {
    slug: "dental",
    path: "/dental-ai-receptionist",
    trade: "Dental",
    headline: "Fill chairs while your front desk focuses on patients in-office.",
    subhead: "Book cleanings, handle emergencies, and capture new patient intake.",
    painPoints: ["Lunch-hour missed calls", "New patient inquiries", "Same-day emergency triage"],
    sampleServices: "Cleanings, crowns, emergency dental, Invisalign consults, new patient intake",
    defaultGreeting: "Thanks for calling the practice — how can we help you today?",
  },
  {
    slug: "legal",
    path: "/legal-ai-receptionist",
    trade: "Legal",
    headline: "Intake every lead without burning paralegal time.",
    subhead: "Screen practice areas, book consults, and capture case details securely.",
    painPoints: ["After-hours DUI / injury calls", "Consult scheduling backlog", "Unqualified lead filtering"],
    sampleServices: "Personal injury, family law, criminal defense, estate planning consults",
    defaultGreeting: "Thank you for calling — may I ask what type of matter you're calling about?",
  },
];

export function getVertical(slug: VerticalSlug): VerticalConfig {
  const v = VERTICALS.find((x) => x.slug === slug);
  if (!v) throw new Error(`Unknown vertical: ${slug}`);
  return v;
}