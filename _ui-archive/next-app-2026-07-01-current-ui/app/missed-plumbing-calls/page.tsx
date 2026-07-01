import type { Metadata } from "next";
import SeoLandingPage, { buildSeoMetadata } from "@/components/marketing/SeoLandingPage";
import { getSeoLandingConfig } from "@/lib/seo-landing-pages";

const config = getSeoLandingConfig("missed-plumbing-calls");

export const metadata: Metadata = buildSeoMetadata(config);

export default function MissedPlumbingCallsPage() {
  return <SeoLandingPage config={config} />;
}