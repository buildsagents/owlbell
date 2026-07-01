import type { Metadata } from "next";
import SeoLandingPage, { buildSeoMetadata } from "@/components/marketing/SeoLandingPage";
import { getSeoLandingConfig } from "@/lib/seo-landing-pages";

const config = getSeoLandingConfig("ai-receptionist-for-plumbers");

export const metadata: Metadata = buildSeoMetadata(config);

export default function AiReceptionistForPlumbersPage() {
  return <SeoLandingPage config={config} />;
}