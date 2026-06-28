"use client";

import PhoneAlert from "@/components/PhoneAlert";

export default function HeroSection() {
  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <section className="hero-dispatch" id="top">
      <div className="hero-dispatch-grid wrap">
        <div className="hero-dispatch-copy">
          <p className="kicker">Plumbing contractors only · US-based agency team</p>
          <h1>
            Every emergency call answered.
            <em> You get the text.</em>
          </h1>
          <p className="hero-dispatch-lead">
            Owlbell is a managed reception agency — not software you configure.
            We answer, qualify, book, and text you the job details before voicemail
            ever picks up.
          </p>

          <div className="hero-dispatch-actions">
            <button
              type="button"
              className="btn btn--copper"
              onClick={() => scrollTo("pricing")}
            >
              Start 7-day trial
            </button>
            <button
              type="button"
              className="btn btn--ghost-light"
              onClick={() => scrollTo("how")}
            >
              How the agency works
            </button>
          </div>

          <div className="hero-dispatch-contact">
            <a href="mailto:hello@owlbell.xyz" className="hero-dispatch-email">
              hello@owlbell.xyz
            </a>
            <span>Questions before you subscribe? We reply within a few hours.</span>
          </div>
        </div>

        <PhoneAlert />
      </div>
    </section>
  );
}