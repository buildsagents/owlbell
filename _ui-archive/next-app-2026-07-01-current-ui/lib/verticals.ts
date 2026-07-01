export type VerticalSlug = "plumbing";

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
    headline: "Every plumbing emergency answered - you get the text.",
    subhead: "24/7 AI receptionist built for UK plumbing contractors.",
    painPoints: ["Burst pipes after hours", "Voicemail during peak season", "Slow callback on estimates"],
    sampleServices: "Leak repair, drain cleaning, water heaters, sewer line, emergency plumbing",
    defaultGreeting: "Thanks for calling - how can we help with your plumbing today?",
  },
];

export function getVertical(slug: VerticalSlug): VerticalConfig {
  const v = VERTICALS.find((x) => x.slug === slug);
  if (!v) throw new Error(`Unknown vertical: ${slug}`);
  return v;
}
