import type { Metadata } from "next";
import Link from "next/link";
import FaqAccordion from "@/components/FaqAccordion";
import TrustPage from "@/components/TrustPage";
import { FAQ_ITEMS } from "@/lib/faq-data";

export const metadata: Metadata = {
  title: "FAQ — Owlbell",
  description:
    "Answers for plumbing contractors: real person vs AI, call recording legality, ServiceTitan integration, go-live timeline, trial, setup fees, and after-hours coverage.",
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
        meta="Straight answers for plumbing shop owners — no sales deck required"
        wide
      >
        <section className="faq-intro">
          <p>
            The questions we hear on intake calls, in email, and from owners who got
            burned by generic answering services. Still stuck?{" "}
            <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a>
          </p>
        </section>

        <FaqAccordion items={FAQ_ITEMS} />

        <section className="faq-footer-cta">
          <h2>Want to hear it before you subscribe?</h2>
          <p>
            <Link href="/demo">Listen to a sample emergency call</Link> or read{" "}
            <Link href="/about">how the agency works</Link>.
          </p>
          <p>
            <Link href="/#pricing" className="btn btn--copper">
              Start 7-day trial
            </Link>
          </p>
        </section>
      </TrustPage>
    </>
  );
}