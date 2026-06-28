"use client";

import RoiCalculator from "@/components/RoiCalculator";

const TRUST_BADGES = [
  {
    id: "trial",
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden>
        <path
          fillRule="evenodd"
          d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm3.857-9.809a.75.75 0 0 0-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 1 0-1.06 1.061l2.5 2.5a.75.75 0 0 0 1.137-.089l4-5.5Z"
          clipRule="evenodd"
        />
      </svg>
    ),
    text: (
      <>
        <strong>White-glove</strong> onboarding
      </>
    ),
  },
  {
    id: "managed",
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden>
        <path
          fillRule="evenodd"
          d="M9.661 2.237a.75.75 0 0 1 .678 0 11.954 11.954 0 0 0 7.825 2.269.75.75 0 0 1 .654.75v6.636a.75.75 0 0 1-.388.657 11.946 11.946 0 0 0-7.825 2.269.75.75 0 0 1-.678 0 11.946 11.946 0 0 0-7.825-2.269.75.75 0 0 1-.388-.657V5.256a.75.75 0 0 1 .654-.75 11.954 11.954 0 0 0 7.825-2.269ZM10 3.5a10.48 10.48 0 0 0-6.5 2.143v5.714A10.48 10.48 0 0 0 10 13.857 10.48 10.48 0 0 0 16.5 11.357V5.643A10.48 10.48 0 0 0 10 3.5Z"
          clipRule="evenodd"
        />
      </svg>
    ),
    text: (
      <>
        <strong>Human-led</strong> setup & support
      </>
    ),
  },
  {
    id: "answer-time",
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden>
        <path d="M11.983 1.907a.75.75 0 0 0-1.292-.657l-8.5 9.5A.75.75 0 0 0 2.75 12h6.352l-1.127 3.995a.75.75 0 0 0 1.292.657l8.5-9.5A.75.75 0 0 0 17.25 8h-6.352l1.085-3.858Z" />
      </svg>
    ),
    text: (
      <>
        <strong>&lt;2s</strong> answer time, 24/7
      </>
    ),
  },
];

export default function HeroSection() {
  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <section className="hero section-hero">
      <div className="wrap hero-grid">
        <div className="hero-copy">
          <span className="hero-eyebrow">AI Receptionist Agency · Plumbing Only</span>
          <h1>Stop Losing $400+ Jobs to Voicemail</h1>
          <p className="hero-sub">
            The premium AI receptionist agency built exclusively for plumbing
            companies. Get every call answered, jobs booked, and owners notified
            — instantly.
          </p>

          <div className="hero-actions">
            <button
              type="button"
              className="agency-btn agency-btn--primary"
              onClick={() => scrollTo("pricing")}
            >
              Start 7-Day Trial
              <span aria-hidden>→</span>
            </button>
            <button
              type="button"
              className="agency-btn agency-btn--secondary"
              onClick={() => scrollTo("how")}
            >
              <span className="hero-play" aria-hidden>
                <svg viewBox="0 0 20 20" fill="currentColor">
                  <path d="M6.3 4.2a1 1 0 0 1 1.52-.85l7.5 4.5a1 1 0 0 1 0 1.7l-7.5 4.5a1 1 0 0 1-1.52-.85V4.2Z" />
                </svg>
              </span>
              Watch How It Works
            </button>
          </div>

          <ul className="hero-trust">
            {TRUST_BADGES.map((badge) => (
              <li key={badge.id} className="hero-trust-pill">
                <span className="hero-trust-icon">{badge.icon}</span>
                <span>{badge.text}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="hero-calculator">
          <RoiCalculator />
        </div>
      </div>
    </section>
  );
}