import type { Metadata } from "next";
import Link from "next/link";
import TrustPage from "@/components/TrustPage";
import ComplianceBadges from "@/components/marketing/ComplianceBadges";
import {
  CTA_PRIMARY,
  CTA_SECONDARY,
  MANAGED_SETUP_KICKER,
  MANAGED_SETUP_STEPS,
  auditHref,
  sampleCallHref,
} from "@/lib/marketing-cta";

export const metadata: Metadata = {
  title: "How Owlbell Works - AI Receptionist Setup & Retell Integration",
  description:
    "Managed setup for plumbing shops: we configure voice and scripts, you forward missed calls, we tune from real calls, you get booked jobs by SMS.",
};

export default function HowItWorksPage() {
  return (
    <TrustPage title="How it works" meta="Managed setup - Retell-powered voice - Forward missed calls">
      <section>
        <p>
          Owlbell runs on Retell AI for natural phone conversations, with TCPA-aware disclosures and encrypted
          storage for transcripts. Our team configures your agent - you forward missed calls and we handle the rest.
        </p>
        <ComplianceBadges />
      </section>
      <section>
        <p>{MANAGED_SETUP_KICKER}</p>
        <ol className="flow-steps">
          {MANAGED_SETUP_STEPS.map((step, i) => (
            <li key={step.id} className="flow-step">
              <span className="flow-step-num num">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <h3>{step.label}</h3>
                <p>{step.detail}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
      <section>
        <Link href={auditHref({ source: "how_it_works" })} className="btn btn--copper">
          {CTA_PRIMARY}
        </Link>
        {" "}
        <Link href={sampleCallHref()} className="btn btn--outline">
          {CTA_SECONDARY}
        </Link>
      </section>
    </TrustPage>
  );
}