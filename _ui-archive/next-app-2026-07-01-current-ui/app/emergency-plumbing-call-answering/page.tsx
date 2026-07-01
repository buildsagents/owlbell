import type { Metadata } from "next";
import SeoLandingPage, { buildSeoMetadata } from "@/components/marketing/SeoLandingPage";
import { getSeoLandingConfig } from "@/lib/seo-landing-pages";

const config = getSeoLandingConfig("emergency-plumbing-call-answering");

export const metadata: Metadata = buildSeoMetadata(config);

export default function EmergencyPlumbingCallAnsweringPage() {
  return <SeoLandingPage config={config} />;
}