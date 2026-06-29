import type { Metadata } from "next";
import Link from "next/link";
import TrustPage from "@/components/TrustPage";
import { CTA_START_TRIAL, onboardingHref } from "@/lib/marketing-cta";

export const metadata: Metadata = {
  title: "Compare — Owlbell vs Receptionist vs Other AI Tools",
  description:
    "Side-by-side comparison of Owlbell AI receptionist vs hiring staff vs generic answering services vs DIY bots.",
};

const OPTIONS = [
  {
    name: "Hire a receptionist",
    cost: "$35k–$48k/yr + benefits",
    pros: "Human rapport during business hours",
    cons: "One person, 40 hrs/wk — nights and weekends still go to voicemail",
  },
  {
    name: "Generic answering service",
    cost: "$200–$800/mo + per-minute",
    pros: "Cheap entry price",
    cons: "Message-taking only — rarely books into your calendar",
  },
  {
    name: "DIY AI phone bot",
    cost: "Low software + high owner time",
    pros: "Flexible if you finish setup",
    cons: "Most owners never complete integrations or emergency scripts",
  },
  {
    name: "Owlbell",
    cost: "From $1,497/mo · self-serve setup",
    pros: "24/7 answering, booking, CRM handoff, live dashboard, <15 min activation",
    cons: "Premium pricing — built for shops that cannot miss high-value calls",
    featured: true,
  },
];

export default function ComparePage() {
  return (
    <TrustPage title="Compare your options" meta="Cost per booked job — not cost per minute">
      <section className="compare-grid">
        {OPTIONS.map((o) => (
          <article key={o.name} className={`compare-card${o.featured ? " compare-card--featured" : ""}`}>
            <h3>{o.name}</h3>
            <p className="compare-cost">{o.cost}</p>
            <p><strong>Pros:</strong> {o.pros}</p>
            <p><strong>Cons:</strong> {o.cons}</p>
          </article>
        ))}
      </section>
      <section>
        <Link href={onboardingHref({ source: "compare" })} className="btn btn--copper">
          {CTA_START_TRIAL}
        </Link>
      </section>
    </TrustPage>
  );
}