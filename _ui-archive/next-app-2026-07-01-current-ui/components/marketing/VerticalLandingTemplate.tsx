import Link from "next/link";
import type { VerticalConfig } from "@/lib/verticals";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";
import TrustBar from "@/components/marketing/TrustBar";
import RoiCalculator from "@/components/RoiCalculator";
import ComplianceBadges from "@/components/marketing/ComplianceBadges";
import { CTA_PRIMARY, CTA_SECONDARY, auditHref, sampleCallHref } from "@/lib/marketing-cta";

type Props = {
  vertical: VerticalConfig;
};

export function VerticalLandingTemplate({ vertical }: Props) {
  return (
    <div className="site">
      <SiteHeader />
      <main className="site-main">
        <section className="hero-dispatch" id="top">
          <div className="hero-dispatch-grid wrap">
            <div className="hero-dispatch-copy">
              <p className="kicker">{vertical.trade} - Managed setup - we handle the rest</p>
              <h1>
                {vertical.headline}
              </h1>
              <p className="hero-dispatch-lead">{vertical.subhead}</p>
              <div className="hero-dispatch-actions">
                <Link href={auditHref({ vertical: vertical.slug })} className="btn btn--copper">
                  {CTA_PRIMARY}
                </Link>
                <Link href={sampleCallHref()} className="btn btn--ghost-light">
                  {CTA_SECONDARY}
                </Link>
              </div>
              <ComplianceBadges />
            </div>
          </div>
        </section>
        <TrustBar />
        <section className="section">
          <div className="wrap">
            <header className="section-lead">
              <p className="kicker kicker--dark">Why {vertical.trade}</p>
              <h2>Scripts and routing tuned for plumbing calls</h2>
            </header>
            <ul className="vertical-bullets">
              {vertical.painPoints.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
            <p className="ob-muted">
              Default greeting: <em>{vertical.defaultGreeting}</em>
            </p>
          </div>
        </section>
        <RoiCalculator />
        <section className="section section--warm">
          <div className="wrap case-study-cta">
            <p>Ready to stop sending leads to voicemail?</p>
            <Link href={auditHref({ vertical: vertical.slug, source: "vertical_cta" })} className="btn btn--copper">
              {CTA_PRIMARY}
            </Link>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

export default VerticalLandingTemplate;