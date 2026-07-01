import type { Metadata } from "next";
import SeoLandingPage, { buildSeoMetadata } from "@/components/marketing/SeoLandingPage";
import { getSeoLandingConfig } from "@/lib/seo-landing-pages";

const config = getSeoLandingConfig("after-hours-plumbing-answering");

export const metadata: Metadata = buildSeoMetadata(config);

export default function AfterHoursPlumbingAnsweringPage() {
  return <SeoLandingPage config={config} />;
}