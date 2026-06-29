import type { Metadata } from "next";
import Link from "next/link";
import TrustPage from "@/components/TrustPage";
import ComplianceBadges from "@/components/marketing/ComplianceBadges";
import { CTA_LAUNCH_AI, onboardingHref } from "@/lib/marketing-cta";

export const metadata: Metadata = {
  title: "How Owlbell Works — AI Receptionist Setup & Retell Integration",
  description:
    "Self-serve onboarding in under 15 minutes: voice selection, knowledge base, calendar, phone forwarding, emergency routing, and live test calls.",
};

const STEPS = [
  { title: "Land & calculate ROI", body: "Use the interactive calculator, pick your vertical, and start free trial — fully self-serve." },
  { title: "Configure in onboarding", body: "Voice, personality, KB upload, Google/Outlook calendar, CRM handoff, hours, and emergency rules." },
  { title: "Activate & test", body: "Your AI provisions immediately. Place a first test call from the confirmation screen." },
  { title: "Monitor in dashboard", body: "Analytics, transcripts, live listen-in, script edits, and billing — mobile-friendly." },
];

export default function HowItWorksPage() {
  return (
    <TrustPage title="How it works" meta="Self-serve · Retell-powered voice · Under 15 minutes to first call">
      <section>
        <p>
          Owlbell runs on Retell AI for natural phone conversations, with TCPA-aware disclosures and encrypted
          storage for transcripts. You configure everything in onboarding — we provision the line and agent automatically.
        </p>
        <ComplianceBadges />
      </section>
      <section>
        <ol className="flow-steps">
          {STEPS.map((step, i) => (
            <li key={step.title} className="flow-step">
              <span className="flow-step-num num">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>
      <section>
        <Link href={onboardingHref({ source: "how_it_works" })} className="btn btn--copper">
          {CTA_LAUNCH_AI}
        </Link>
        {" "}
        <Link href="/demo" className="btn btn--outline">
          Try demo sandbox
        </Link>
      </section>
    </TrustPage>
  );
}