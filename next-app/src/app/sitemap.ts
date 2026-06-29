import type { MetadataRoute } from "next";
import { VERTICALS } from "@/lib/verticals";

const SITE_URL = "https://owlbell.xyz";

export default function sitemap(): MetadataRoute.Sitemap {
  const lastModified = new Date();

  const staticPages = [
    "",
    "/privacy",
    "/terms",
    "/onboarding",
    "/faq",
    "/about",
    "/demo",
    "/how-it-works",
    "/compare",
  ].map((path) => ({
    url: `${SITE_URL}${path}`,
    lastModified,
    changeFrequency: path === "" ? ("weekly" as const) : ("monthly" as const),
    priority: path === "" ? 1 : path === "/onboarding" ? 0.9 : 0.7,
  }));

  const verticalPages = VERTICALS.map((v) => ({
    url: `${SITE_URL}${v.path}`,
    lastModified,
    changeFrequency: "weekly" as const,
    priority: 0.9,
  }));

  return [...staticPages, ...verticalPages];
}