import type { Metadata } from "next";
import VerticalLandingTemplate from "@/components/marketing/VerticalLandingTemplate";
import { getVertical } from "@/lib/verticals";

const vertical = getVertical("hvac");
const SITE_URL = "https://owlbell.xyz";

export const metadata: Metadata = {
  title: "AI Receptionist for HVAC — 24/7 Answering | Owlbell",
  description: vertical.subhead,
  alternates: { canonical: `${SITE_URL}${vertical.path}` },
};

export default function HvacAiReceptionistPage() {
  return <VerticalLandingTemplate vertical={vertical} />;
}