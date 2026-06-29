import type { Metadata } from "next";
import Link from "next/link";
import FaqSearch from "@/components/FaqSearch";
import TrustPage from "@/components/TrustPage";
import { FAQ_ITEMS } from "@/lib/faq-data";
import { CTA_START_TRIAL, onboardingHref } from "@/lib/marketing-cta";

export const metadata: Metadata = {
  title: "FAQ — Owlbell AI Receptionist",
  description:
    "Self-serve setup, go-live in under 15 minutes, ServiceTitan integration, call recording compliance, trial terms, and after-hours coverage.",
};

const faqSchema = {
  "@context": "https://schema.org",
  "@type": "FAQPage",
  mainEntity: FAQ_ITEMS.map((item) => ({
    "@type": "Question",
    name: item.question,
    acceptedAnswer: {
      "@type": "Answer",
      text: item.answer,
    },
  })),
};

export default function FaqPage() {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
      />
      <TrustPage
        title="Frequently asked questions"
        meta="Straight answers for service business owners — searchable, no sales deck required"
        wide
      >
        <section className="faq-intro">
          <p>
            Self-serve onboarding, compliance, integrations, and go-live timing. Still stuck?{" "}
            <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a>
          </p>
        </section>

        <FaqSearch items={FAQ_ITEMS} />

        <section className="faq-footer-cta">
          <h2>Ready to launch?</h2>
          <p>
            <Link href="/demo">Try the demo sandbox</Link> or{" "}
            <Link href="/how-it-works">read how it works</Link>.
          </p>
          <p>
            <Link href={onboardingHref({ source: "faq" })} className="btn btn--copper">
              {CTA_START_TRIAL}
            </Link>
          </p>
        </section>
      </TrustPage>
    </>
  );
}