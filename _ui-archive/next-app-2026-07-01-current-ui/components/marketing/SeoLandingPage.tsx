import Link from "next/link";
import CallScenarioChips from "@/components/CallScenarioChips";
import HeroOpsVisual from "@/components/HeroOpsVisual";
import RoiCalculator from "@/components/RoiCalculator";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";
import TrustBar from "@/components/marketing/TrustBar";
import ComplianceBadges from "@/components/marketing/ComplianceBadges";
import {
  CTA_PRIMARY,
  CTA_SECONDARY,
  MANAGED_SETUP_STEPS,
  auditHref,
  sampleCallHref,
} from "@/lib/marketing-cta";
import { buildSeoJsonLd, seoPageUrl, type SeoLandingConfig } from "@/lib/seo-landing-pages";

type Props = {
  config: SeoLandingConfig;
};

export default function SeoLandingPage({ config }: Props) {
  const jsonLd = buildSeoJsonLd(config);

  return (
    <div className="site">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <SiteHeader />

      <main className="site-main">
        <section className="hero-dispatch" id="top">
          <div className="hero-dispatch-grid wrap">
            <div className="hero-dispatch-copy">
              <p className="kicker">{config.hero.kicker}</p>
              <h1>
                {config.hero.headline}
                {config.hero.headlineEm ? <em>{config.hero.headlineEm}</em> : null}
              </h1>
              <p className="hero-dispatch-lead">{config.hero.lead}</p>
              <div className="hero-dispatch-actions">
                <Link
                  href={auditHref({ source: config.source })}
                  className="btn btn--copper"
                >
                  {CTA_PRIMARY}
                </Link>
                <Link href={sampleCallHref()} className="btn btn--ghost-light">
                  {CTA_SECONDARY}
                </Link>
              </div>
              <CallScenarioChips limit={3} className="hero-scenarios" />
              <ComplianceBadges />
            </div>

            {config.timeline ? (
              <aside className="seo-hero-aside">
                <p className="kicker kicker--dark">Typical after-hours call</p>
                <ol className="case-study-timeline">
                  {config.timeline.map((step, i) => (
                    <li key={`${step.time}-${i}`}>
                      <time className="num">{step.time}</time>
                      <span>{step.event}</span>
                    </li>
                  ))}
                </ol>
                <p className="seo-hero-note">
                  Anonymized workflow example.{" "}
                  <Link href="/demo">Try the live Retell demo</Link>
                </p>
              </aside>
            ) : (
              <HeroOpsVisual />
            )}
          </div>
        </section>

        <TrustBar />

        {config.sections.map((section) => (
          <section
            key={section.id}
            id={section.id}
            className={`section${section.warm ? " section--warm" : ""}`}
          >
            <div className="wrap">
              <header className="section-lead">
                <p className="kicker kicker--dark">{section.kicker}</p>
                <h2>{section.title}</h2>
                {section.intro ? <p>{section.intro}</p> : null}
              </header>

              {section.stats && section.stats.length > 0 && (
                <dl className="case-study-stats seo-stats-row">
                  {section.stats.map((stat) => (
                    <div key={stat.label}>
                      <dt>{stat.label}</dt>
                      <dd className="num">{stat.value}</dd>
                    </div>
                  ))}
                </dl>
              )}

              <div className="seo-prose legal-body">
                {section.paragraphs.map((p, i) => (
                  <p key={i}>{p}</p>
                ))}
              </div>

              {section.bullets && section.bullets.length > 0 && (
                <ul className="vertical-bullets seo-landing-bullets">
                  {section.bullets.map((b) => (
                    <li key={b}>{b}</li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        ))}

        <section className="section section--ink" id="how-it-works">
          <div className="wrap">
            <header className="section-lead">
              <p className="kicker">How it works</p>
              <h2>Managed setup - no tech work on your end</h2>
            </header>
            <ol className="flow-steps seo-flow-steps--ink">
              {MANAGED_SETUP_STEPS.map((step, index) => (
                <li key={step.id} className="flow-step">
                  <span className="flow-step-num num">{String(index + 1).padStart(2, "0")}</span>
                  <div>
                    <h3>{step.label}</h3>
                    <p>{step.detail}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <RoiCalculator />

        <section className="section section--warm">
          <div className="wrap case-study-cta">
            <p>Ready to see your shop&apos;s numbers?</p>
            <Link
              href={auditHref({ source: `${config.source}_cta` })}
              className="btn btn--copper"
            >
              {CTA_PRIMARY}
            </Link>
            <p className="seo-landing-footer-links">
              <Link href="/faq">FAQ</Link>
              {" - "}
              <Link href="/demo">Live demo</Link>
              {" - "}
              <Link href="/">Home</Link>
            </p>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}

export function buildSeoMetadata(config: SeoLandingConfig) {
  const url = seoPageUrl(config.path);
  return {
    title: config.metadata.title,
    description: config.metadata.description,
    alternates: { canonical: url },
    openGraph: {
      type: "website" as const,
      url,
      title: config.metadata.title,
      description: config.metadata.description,
    },
  };
}
