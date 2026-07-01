import type { Metadata } from "next";
import { notFound } from "next/navigation";
import SeoLandingPage, { buildSeoMetadata } from "@/components/marketing/SeoLandingPage";
import { getAllCitySlugs, getCitySeoConfig } from "@/lib/city-seo-pages";

type Props = {
  params: Promise<{ city: string }>;
};

export function generateStaticParams() {
  return getAllCitySlugs().map((city) => ({ city }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { city } = await params;
  const config = getCitySeoConfig(city);
  if (!config) return {};
  return buildSeoMetadata(config);
}

export default async function CityPlumbersPage({ params }: Props) {
  const { city } = await params;
  const config = getCitySeoConfig(city);
  if (!config) notFound();
  return <SeoLandingPage config={config} />;
}