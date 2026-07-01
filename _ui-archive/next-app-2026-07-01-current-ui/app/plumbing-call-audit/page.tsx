import type { Metadata } from "next";
import SeoLandingPage, { buildSeoMetadata } from "@/components/marketing/SeoLandingPage";
import { getSeoLandingConfig } from "@/lib/seo-landing-pages";

const config = getSeoLandingConfig("plumbing-call-audit");

export const metadata: Metadata = buildSeoMetadata(config);

export default function PlumbingCallAuditPage() {
  return <SeoLandingPage config={config} />;
}