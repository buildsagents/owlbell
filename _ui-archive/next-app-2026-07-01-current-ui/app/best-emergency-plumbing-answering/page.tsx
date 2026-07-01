import type { Metadata } from "next";
import SeoLandingPage, { buildSeoMetadata } from "@/components/marketing/SeoLandingPage";
import { NICHE_SEO_PAGE } from "@/lib/city-seo-pages";

export const metadata: Metadata = buildSeoMetadata(NICHE_SEO_PAGE);

export default function BestEmergencyPlumbingAnsweringPage() {
  return <SeoLandingPage config={NICHE_SEO_PAGE} />;
}