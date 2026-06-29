import type { Metadata } from "next";
import VerticalLandingTemplate from "@/components/marketing/VerticalLandingTemplate";
import { getVertical } from "@/lib/verticals";

const vertical = getVertical("legal");
const SITE_URL = "https://owlbell.xyz";

export const metadata: Metadata = {
  title: "AI Receptionist for Law Firms — 24/7 Intake | Owlbell",
  description: vertical.subhead,
  alternates: { canonical: `${SITE_URL}${vertical.path}` },
};

export default function LegalAiReceptionistPage() {
  return <VerticalLandingTemplate vertical={vertical} />;
}