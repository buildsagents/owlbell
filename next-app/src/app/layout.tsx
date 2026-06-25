import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const plusJakarta = Plus_Jakarta_Sans({
  variable: "--font-plus-jakarta-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Owlbell — Your 24/7 AI Receptionist | Never Miss a Call Again",
  description: "Owlbell answers your business calls 24/7, books appointments, and texts you every message instantly. For HVAC, plumbing, electrical, roofing, pest control & property managers. From $297/mo. Hear it live.",
  keywords: "AI phone answering service, virtual receptionist, AI receptionist for contractors, HVAC answering service, plumbing answering service, 24/7 call answering, missed call solution",
  openGraph: {
    title: "Owlbell — Never Miss a Call Again",
    description: "A 24/7 AI receptionist that answers, books jobs, and texts you instantly. From $297/mo.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${plusJakarta.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
