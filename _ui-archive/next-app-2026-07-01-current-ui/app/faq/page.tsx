import type { Metadata } from "next";
import Link from "next/link";
import FaqSearch from "@/components/FaqSearch";
import TrustPage from "@/components/TrustPage";
import { FAQ_ITEMS } from "@/lib/faq-data";
import { CTA_PRIMARY, CTA_SECONDARY, auditHref, sampleCallHref } from "@/lib/marketing-cta";

export const metadata: Metadata = {
  title: "FAQ - Owlbell AI Receptionist",
  description:
    "Is Owlbell a real company? Who sets it up? What if AI gets it wrong? Recording legality, Jobber/ServiceTitan/Housecall Pro, after-hours coverage, and cancellation.",
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
        meta="Straight answers for service business owners - searchable, no sales deck required"
        wide
      >
        <section className="faq-intro">
          <p>
            Eight questions every plumbing owner asks - plus go-live timing, pricing, and data
            ownership. Still stuck?{" "}
            <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a>
          </p>
        </section>

        <FaqSearch items={FAQ_ITEMS} />

        <section className="faq-footer-cta">
          <h2>Ready to see your numbers?</h2>
          <p>
            <Link href={auditHref({ source: "faq" })} className="btn btn--copper">
              {CTA_PRIMARY}
            </Link>
            {" "}
            <Link href={sampleCallHref()} className="btn btn--outline">
              {CTA_SECONDARY}
            </Link>
          </p>
        </section>
      </TrustPage>
    </>
  );
}