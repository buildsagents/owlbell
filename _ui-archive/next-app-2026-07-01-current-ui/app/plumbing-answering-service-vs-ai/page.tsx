import type { Metadata } from "next";
import SeoLandingPage, { buildSeoMetadata } from "@/components/marketing/SeoLandingPage";
import { getSeoLandingConfig } from "@/lib/seo-landing-pages";

const config = getSeoLandingConfig("plumbing-answering-service-vs-ai");

export const metadata: Metadata = buildSeoMetadata(config);

export default function PlumbingAnsweringServiceVsAiPage() {
  return <SeoLandingPage config={config} />;
}