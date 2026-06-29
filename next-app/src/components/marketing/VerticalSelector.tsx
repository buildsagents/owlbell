import Link from "next/link";
import { VERTICALS } from "@/lib/verticals";
import { onboardingHref } from "@/lib/marketing-cta";

export function VerticalSelector() {
  return (
    <section className="section section--warm" id="verticals">
      <div className="wrap">
        <header className="section-lead section-lead--center">
          <p className="kicker kicker--dark">Your trade</p>
          <h2>Built for service businesses — not generic call centers</h2>
          <p>Pick your vertical for tailored scripts, FAQs, and emergency routing defaults.</p>
        </header>
        <div className="vertical-selector-grid">
          {VERTICALS.map((v) => (
            <Link key={v.slug} href={v.path} className="vertical-selector-card">
              <span className="vertical-selector-trade">{v.trade}</span>
              <span className="vertical-selector-headline">{v.headline}</span>
            </Link>
          ))}
        </div>
        <p className="vertical-selector-cta">
          <Link href={onboardingHref()} className="btn btn--copper">
            Launch Your AI Receptionist
          </Link>
        </p>
      </div>
    </section>
  );
}

export default VerticalSelector;