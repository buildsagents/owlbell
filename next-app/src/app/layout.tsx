import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
});

const SITE_URL = "https://owlbell.xyz";
const SITE_TITLE = "Owlbell - AI operations for plumbing companies";
const SITE_DESCRIPTION =
  "Owlbell is being rebuilt as a managed AI front office for UK plumbing companies.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: SITE_TITLE,
  description: SITE_DESCRIPTION,
  keywords: [
    "AI operations",
    "AI front office",
    "plumbing operations",
    "missed call recovery",
    "quote follow up",
    "Owlbell",
  ],
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: "Owlbell",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    locale: "en_GB",
    images: [{ url: "/og.svg", width: 1200, height: 630, alt: "Owlbell" }],
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    images: ["/og.svg"],
  },
  alternates: { canonical: SITE_URL },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "Owlbell",
  url: SITE_URL,
  email: "hello@owlbell.xyz",
  description: SITE_DESCRIPTION,
  areaServed: "GB",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <head>
        <meta name="view-transition" content="same-origin" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
