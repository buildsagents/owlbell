"use client";

import Link from "next/link";
import PhoneAlert from "@/components/PhoneAlert";
import ComplianceBadges from "@/components/marketing/ComplianceBadges";
import { CTA_LAUNCH_AI, CTA_START_TRIAL, DEMO_PATH, onboardingHref } from "@/lib/marketing-cta";

export default function HeroSection() {
  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <section className="hero-dispatch" id="top">
      <div className="hero-dispatch-grid wrap">
        <div className="hero-dispatch-copy">
          <p className="kicker">Join 50+ service businesses · Self-serve in under 15 minutes</p>
          <h1>
            Your AI Receptionist Answers Every Call,
            <em> Books Every Job</em> — 24/7
          </h1>
          <p className="hero-dispatch-lead">
            Owlbell is your AI receptionist for plumbing, HVAC, electrical, dental, legal, and more.
            Configure voice, scripts, calendar, and routing yourself — then place your first test call
            before you leave onboarding.
          </p>

          <div className="hero-dispatch-actions">
            <Link href={onboardingHref({ source: "hero" })} className="btn btn--copper">
              {CTA_LAUNCH_AI}
            </Link>
            <Link href={onboardingHref({ source: "hero_trial" })} className="btn btn--ghost-light">
              {CTA_START_TRIAL}
            </Link>
            <button type="button" className="btn btn--ghost-light" onClick={() => scrollTo("honest-math")}>
              See your exact ROI
            </button>
          </div>

          <ComplianceBadges />

          <div className="hero-dispatch-contact">
            <Link href={DEMO_PATH} className="hero-dispatch-email">
              Try demo sandbox →
            </Link>
            <span>Recorded calls + interactive sample — no human sales call required.</span>
          </div>
        </div>

        <PhoneAlert />
      </div>
    </section>
  );
}