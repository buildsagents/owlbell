import Link from "next/link";
import HeroOpsVisual from "@/components/HeroOpsVisual";

function HeroStat({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div className="hero-stat-value num">{value}</div>
      <span className="hero-stat-label">{label}</span>
    </div>
  );
}

export default function HeroSection() {
  return (
    <section className="hero" id="top">
      <div className="wrap hero-grid">
        <div className="hero-copy">
          <span className="hero-kicker">Managed AI front office for plumbing companies</span>
          <h1>The AI front office for plumbing companies.</h1>
          <p>
            Owlbell answers your calls, texts back missed callers, follows up
            quotes, and requests reviews. All the front-office work that wins
            jobs, without another admin hire.
          </p>
          <ul className="hero-proof-list" aria-label="What Owlbell handles">
            <li>Answers calls 24/7 and texts back missed callers within the minute</li>
            <li>Follows up quotes, requests reviews, and reactivates old customers</li>
            <li>Weekly report on the revenue you recovered, done for you</li>
          </ul>
          <div className="hero-actions">
            <Link href="/onboarding?source=hero" className="btn btn--primary btn--lg">
              Get Free AI Ops Audit
            </Link>
            <Link href="/demo" className="btn btn--secondary btn--lg">
              Try Call Demo
            </Link>
          </div>
        </div>

        <div className="hero-visual-wrap">
          <div className="hero-live-badge">
            <span className="hero-live-dot" aria-hidden />
            Live overflow board
          </div>
          <HeroOpsVisual />
        </div>

        <div className="hero-stats">
          <HeroStat value="1.8s" label="Typical pickup" />
          <HeroStat value="0" label="Voicemail target" />
          <HeroStat value="£850" label="Example emergency value" />
          <HeroStat value="7 days" label="Trial before launch" />
        </div>
      </div>
    </section>
  );
}
