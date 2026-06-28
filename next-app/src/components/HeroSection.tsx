"use client";

import RoiCalculator from "@/components/RoiCalculator";

const TRUST_BADGES = [
  {
    id: "answer-time",
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden>
        <path d="M11.983 1.907a.75.75 0 0 0-1.292-.657l-8.5 9.5A.75.75 0 0 0 2.75 12h6.352l-1.127 3.995a.75.75 0 0 0 1.292.657l8.5-9.5A.75.75 0 0 0 17.25 8h-6.352l1.085-3.858Z" />
      </svg>
    ),
    text: (
      <>
        <strong>&lt;2s</strong> answer time
      </>
    ),
  },
  {
    id: "guarantee",
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
        <strong>Managed</strong> setup and tuning
      </>
    ),
  },
  {
    id: "coverage",
    icon: (
      <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden>
        <path
          fillRule="evenodd"
          d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm.75-13a.75.75 0 0 0-1.5 0v5c0 .414.336.75.75.75h4a.75.75 0 0 0 0-1.5h-3.25V5Z"
          clipRule="evenodd"
        />
      </svg>
    ),
    text: (
      <>
        <strong>24/7</strong> coverage
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
          <h1>Stop Losing $400 Jobs to Voicemail</h1>
          <p className="hero-sub">
            Plumbing companies get every call answered 24/7. We handle emergency
            calls, book jobs on your calendar, and text you the details, with AI
            built for the trades and real humans managing setup, scripts, and tuning.
          </p>

          <div className="hero-actions">
            <button
              type="button"
              className="agency-btn agency-btn--primary"
              onClick={() => scrollTo("pricing")}
            >
              Book a Growth Strategy Call
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
              See How It Works
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
