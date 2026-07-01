import type { Metadata } from "next";
import Link from "next/link";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";
import {
  CTA_PRIMARY,
  CTA_SECONDARY,
  MANAGED_SETUP_KICKER,
  MANAGED_SETUP_STEPS,
  auditHref,
  sampleCallHref,
} from "@/lib/marketing-cta";

const SITE_URL = "https://owlbell.xyz";
const PAGE_URL = `${SITE_URL}/plumbing-ai-receptionist`;

export const metadata: Metadata = {
  title: "AI Receptionist for Plumbers - 24/7 Plumbing Answering Service | Owlbell",
  description:
    "Managed AI receptionist built for UK plumbing contractors. Answer after-hours emergencies, capture every lead, and book jobs - without hiring staff or a generic call center. Plans from £1,197/mo.",
  alternates: {
    canonical: PAGE_URL,
  },
  openGraph: {
    type: "website",
    url: PAGE_URL,
    title: "AI Receptionist for Plumbers - Owlbell",
    description:
      "Plumbing AI answering service. Managed setup - forward missed calls, we handle the rest. Emergencies flagged, jobs booked, owner texted 24/7.",
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebPage",
      "@id": `${PAGE_URL}#webpage`,
      url: PAGE_URL,
      name: "AI Receptionist for Plumbers",
      description:
        "How Owlbell provides managed AI phone answering for UK plumbing contractors - after-hours emergencies, missed-call recovery, and white-glove setup.",
      isPartOf: { "@id": `${SITE_URL}/#website` },
      about: { "@id": `${PAGE_URL}#service` },
      inLanguage: "en-GB",
    },
    {
      "@type": "Service",
      "@id": `${PAGE_URL}#service`,
      name: "Owlbell AI Receptionist for Plumbers",
      serviceType: "AI phone answering service for plumbing contractors",
      provider: {
        "@type": "Organization",
        name: "Owlbell",
        url: SITE_URL,
        email: "hello@owlbell.xyz",
      },
      areaServed: {
        "@type": "Country",
        name: "United Kingdom",
      },
      audience: {
        "@type": "BusinessAudience",
        audienceType: "Plumbing contractors",
      },
      description:
        "Managed AI receptionist that answers inbound plumbing calls 24/7, qualifies emergencies, books appointments on your calendar, and texts job summaries to the owner.",
      offers: {
        "@type": "Offer",
        url: `${SITE_URL}/#pricing`,
        priceCurrency: "GBP",
        price: "1497",
        description: "Launch plan from £1,197/mo with 7-day trial",
      },
    },
  ],
};



export default function PlumbingAiReceptionistPage() {
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
              <p className="kicker">{MANAGED_SETUP_KICKER}</p>
              <h1>
                AI receptionist for plumbers.
                <em> Every call answered.</em>
              </h1>
              <p className="hero-dispatch-lead">
                Managed AI receptionist built for plumbers - we set it up, you forward missed
                calls, we tune the script. Answer after-hours emergencies, book jobs on your
                calendar, and get owner texts before voicemail picks up.
              </p>
              <div className="hero-dispatch-actions">
                <Link href={auditHref({ vertical: "plumbing", source: "plumbing_page" })} className="btn btn--copper">
                  {CTA_PRIMARY}
                </Link>
                <Link href={sampleCallHref()} className="btn btn--ghost-light">
                  {CTA_SECONDARY}
                </Link>
              </div>
              <div className="hero-dispatch-contact">
                <a href="mailto:hello@owlbell.xyz" className="hero-dispatch-email">
                  hello@owlbell.xyz
                </a>
                <span>
                  Questions about fit? Read our <Link href="/faq">FAQ</Link> or{" "}
                  <Link href="/about">about Owlbell</Link>.
                </span>
              </div>
            </div>

            <div className="seo-hero-aside">
              <p className="kicker kicker--dark">Typical Tuesday, 9:47 PM</p>
              <ol className="case-study-timeline">
                <li>
                  <time className="num">9:47 PM</time>
                  <span>Homeowner calls - active leak under kitchen sink</span>
                </li>
                <li>
                  <time className="num">9:47 PM</time>
                  <span>Answered in under 2 seconds; emergency tier confirmed</span>
                </li>
                <li>
                  <time className="num">9:49 PM</time>
                  <span>First available morning slot booked; address captured</span>
                </li>
                <li>
                  <time className="num">9:49 PM</time>
                  <span>Owner SMS: caller, issue, window, map link</span>
                </li>
              </ol>
              <p className="seo-hero-note">
                Composite workflow example - not a named client quote.{" "}
                <Link href="/">See how Owlbell works on the homepage</Link>.
              </p>
            </div>
          </div>
        </section>

        <section className="section" id="after-hours">
          <div className="wrap">
            <header className="section-lead">
              <p className="kicker kicker--dark">After-hours emergencies</p>
              <h2>Plumbing emergencies do not wait for business hours</h2>
              <p>
                Burst pipes, sewer backups, and no-hot-water calls spike between 6 PM and
                midnight - exactly when your crew is off the clock and your office line
                goes to voicemail. That is when homeowners are most anxious and most likely
                to dial the next company on Google.
              </p>
            </header>

            <div className="seo-prose legal-body">
              <p>
                A plumbing AI receptionist is not a replacement for 911 or gas-line
                emergencies you tell callers to escalate immediately. It is a front door for
                legitimate service requests: active leaks, clogged main lines, failed water
                heaters, and commercial no-water situations where waiting until morning
                means real property damage.
              </p>
              <p>
                Generic answering services read a script and take a message. Owlbell is
                configured for plumbing workflows - asking the right diagnostic questions
                (Is water actively flowing? Can you shut off the main? Is this a rental
                property?), applying your after-hours fee disclosure, and routing true
                emergencies to your on-call tech while booking next-day slots for
                non-urgent work.
              </p>
              <p>
                The economics are straightforward. One booked emergency often covers a month
                of service at typical plumbing ticket sizes. Shops running Google Ads or
                Local Services Ads pay for every click; letting those leads hit voicemail
                after hours is one of the most expensive mistakes in the trade.
              </p>
            </div>
          </div>
        </section>

        <section className="section section--warm" id="missed-call-cost">
          <div className="wrap">
            <header className="section-lead">
              <p className="kicker kicker--dark">Missed call cost</p>
              <h2>What one week of voicemail actually costs a plumbing shop</h2>
              <p>
                Most owners underestimate missed calls because they never see the ones that
                never leave a message. Industry studies on home services consistently show
                high hang-up rates when calls go unanswered - callers move to the next
                listing within seconds.
              </p>
            </header>

            <dl className="case-study-stats seo-stats-row">
              <div>
                <dt>Conservative miss rate</dt>
                <dd className="num">8-15 calls / week</dd>
              </div>
              <div>
                <dt>Average booked job</dt>
                <dd className="num">£350-£600</dd>
              </div>
              <div>
                <dt>Monthly revenue at risk</dt>
                <dd className="num">£5,600-£36,000</dd>
              </div>
            </dl>

            <div className="seo-prose legal-body">
              <p>
                Use your own numbers. If your shop misses ten calls per week and converts
                even half of answered calls into booked jobs at a £400 average ticket, that
                is roughly <strong>£800 per week</strong> - about{" "}
                <strong>£3,200 per month</strong> - sitting in voicemail. Emergency calls
                skew higher; a single after-hours water heater replacement can exceed £1,200.
              </p>
              <p>
                Office staff calling back the next morning often reach a homeowner who already
                booked a competitor. Speed-to-answer matters more in plumbing than in
                slower-cycle trades because water damage compounds hourly. An AI receptionist
                for plumbers does not eliminate the need for great technicians; it stops
                qualified demand from leaking out of your funnel.
              </p>
              <p>
                Owlbell Launch{" "}
                <Link href="/#pricing">pays for itself at 3-5 booked jobs/month</Link> (£1,197/mo
                with a 7-day test period). At a £400
                average job, breakeven is roughly four booked calls per month - often one
                emergency and one standard service call. Shops below that volume may not be
                ready for premium answering; we say that plainly on our{" "}
                <Link href="/">homepage ROI section</Link>.
              </p>
            </div>
          </div>
        </section>

        <section className="section" id="vs-answering-service">
          <div className="wrap">
            <header className="section-lead">
              <p className="kicker kicker--dark">Comparison</p>
              <h2>Plumbing AI answering service vs. traditional call centers</h2>
              <p>
                National answering services handle dentists, law firms, and HVAC in the same
                queue. Owlbell is trade-tuned and managed - plumbing scripts configured for you.
              </p>
            </header>

            <div className="call-flow-track seo-compare-track">
              <article className="call-flow-step">
                <span className="call-flow-index num">Option A</span>
                <h3>Generic answering service</h3>
                <p>
                  £200-£800/mo plus per-minute fees. Agents follow a generic script, take
                  messages, and rarely book into your calendar. Emergency nuance - shutoff
                  location, active flow, tenant vs. owner - is often lost.
                </p>
              </article>
              <article className="call-flow-step">
                <span className="call-flow-index num">Option B</span>
                <h3>DIY AI phone bot</h3>
                <p>
                  Low monthly software cost but high owner time cost. You write prompts,
                  test edge cases, fix integrations, and hope nothing breaks during a holiday
                  weekend. Most plumbers never finish setup.
                </p>
              </article>
              <article className="call-flow-step seo-compare-featured">
                <span className="call-flow-index num">Option C</span>
                <h3>Owlbell managed model</h3>
                <p>
                  £1,197-£7,997/mo. We configure plumbing scripts, calendar rules, and emergency
                  routing for you. 24/7 answering, owner SMS summaries, script tuning from real
                  calls - dedicated support on Growth and Scale.
                </p>
              </article>
            </div>

            <div className="seo-prose legal-body">
              <p>
                Price alone misleads. A £300 answering service that captures messages but
                never books costs more than a managed service that converts calls into
                calendar events. The right question is cost per <em>booked job</em>, not
                cost per minute.
              </p>
              <p>
                Owlbell also differs on transparency. Call transcripts and summaries live in
                your dashboard. You hear how emergencies are triaged and can request script
                changes without opening a ticket with an anonymous call center pool. For more
                detail on guarantees and terms, see our <Link href="/faq">FAQ</Link> and{" "}
                <Link href="/terms">terms of service</Link>.
              </p>
            </div>
          </div>
        </section>

        <section className="section section--warm" id="vs-receptionist">
          <div className="wrap">
            <header className="section-lead">
              <p className="kicker kicker--dark">Staffing math</p>
              <h2>AI receptionist vs. hiring a full-time office person</h2>
              <p>
                A capable dispatcher-receptionist is worth every penny - when you can find
                one, train them on plumbing terminology, and keep them through busy season.
                Many shops cannot justify a second office seat until revenue supports it.
              </p>
            </header>

            <div className="seo-prose legal-body">
              <p>
                A full-time receptionist in the US often costs{" "}
                <strong>£35,000-£48,000 per year</strong> in wages alone, before payroll
                taxes, benefits, PTO coverage, and training. That person works roughly 40
                hours per week. Plumbing emergencies happen all 168. Covering nights and
                weekends means overtime, on-call stipends, or a second hire.
              </p>
              <p>
                Part-time help leaves gaps. The Friday 7 PM burst-pipe call lands when nobody
                is at the desk. Hiring a receptionist also does not solve simultaneous rings
                during Monday morning rush - one person can only talk to one homeowner at a
                time.
              </p>
              <p>
                Owlbell is not a moral argument against human staff. Many Growth-plan clients
                keep a daytime office manager and use Owlbell for overflow, lunch coverage,
                and after-hours. The AI receptionist handles the long tail of calls that
                would otherwise hit voicemail; your people handle relationship-heavy
                follow-up and in-office walk-ins.
              </p>
              <p>
                If you are deciding between a first office hire and managed answering,
                consider call volume and average job value. Shops above 80 inbound calls per
                month with strong emergency mix often benefit from both - human during peak
                hours, AI coverage everywhere else.{" "}
                <Link href="/about">Learn how we work with plumbing shops</Link>.
              </p>
            </div>
          </div>
        </section>

        <section className="section section--ink" id="how-it-works">
          <div className="wrap">
            <header className="section-lead">
              <p className="kicker">How it works</p>
              <h2>Four steps - no tech work on your end</h2>
              <p>{MANAGED_SETUP_KICKER}</p>
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

            <div className="seo-prose seo-prose--ink">
              <p>
                Most shops go live within a few business days: start trial, share your shop
                details, forward missed calls, and start getting booked jobs by SMS. Growth and
                Scale plans add CRM handoff, missed-call recovery workflows, and dedicated success
                contact.
              </p>
              <p>
                Want to hear the voice experience before committing?{" "}
                <Link href="/demo">Try the interactive demo call</Link> - it uses the same
                plumbing-oriented conversation patterns we deploy for clients.
              </p>
            </div>
          </div>
        </section>

        <section className="section" id="pricing">
          <div className="wrap">
            <header className="section-lead section-lead--center">
              <p className="kicker kicker--dark">Pricing</p>
              <h2>Pricing that only makes sense if you&apos;re booking jobs</h2>
              <p>
                Think in recovered jobs, not software seats - with managed setup and a 7-day
                test period on every plan.
              </p>
            </header>

            <ul className="pricing-qualifiers" aria-label="Who this is for">
              <li>Best for 40+ inbound calls/month</li>
              <li>Not for brand-new shops</li>
              <li>No long contract</li>
              <li>7-day test period</li>
              <li>Setup handled by Owlbell</li>
            </ul>

            <div className="seo-pricing-cards">
              <article className="pricing-ticket">
                <h3>Launch</h3>
                <p className="pricing-ticket-payoff">
                  Pays for itself if it recovers 3-5 plumbing jobs/month.
                </p>
                <p className="pricing-ticket-rate num">£1,197/mo</p>
                <p className="pricing-ticket-blurb">
                  24/7 answering, emergency routing, owner alerts, 30-day script tuning.
                </p>
              </article>
              <article className="pricing-ticket pricing-ticket--featured">
                <span className="pricing-ticket-tag">Recommended</span>
                <h3>Growth</h3>
                <p className="pricing-ticket-payoff">
                  Pays for itself at ~10-12 booked jobs/month.
                </p>
                <p className="pricing-ticket-rate num">£3,997/mo</p>
                <p className="pricing-ticket-setup">+ £4,000 one-time setup</p>
                <p className="pricing-ticket-blurb">
                  Calendar booking, CRM handoff, missed-call recovery, monthly revenue review.
                </p>
              </article>
              <article className="pricing-ticket">
                <h3>Scale</h3>
                <p className="pricing-ticket-payoff">
                  For multi-location shops booking 25+ jobs/month from overflow.
                </p>
                <p className="pricing-ticket-rate num">£7,997+/mo</p>
                <p className="pricing-ticket-blurb">
                  Multi-location, custom SLAs, dedicated success lead.
                </p>
              </article>
            </div>

            <div className="seo-prose legal-body">
              <p>
                Full feature breakdown, checkout, and the Growth booking guarantee are on the{" "}
                <Link href="/#pricing">main pricing section</Link>. Annual billing locks your
                rate for the term. Cancel during the 7-day trial if coverage is not a fit.
              </p>
            </div>

            <div className="case-study-cta">
              <p>Ready to stop sending emergencies to voicemail?</p>
              <Link href={auditHref({ vertical: "plumbing", source: "plumbing_cta" })} className="btn btn--copper">
                {CTA_PRIMARY}
              </Link>
            </div>
          </div>
        </section>

        <section className="section section--warm" id="who-its-for">
          <div className="wrap">
            <header className="section-lead">
              <p className="kicker kicker--dark">Who it&apos;s for</p>
              <h2>Who a plumbing AI receptionist is built for</h2>
            </header>

            <div className="seo-prose legal-body">
              <p>
                Owlbell is designed for established UK plumbing contractors - residential
                and light commercial - who already invest in lead generation and feel pain
                from missed calls. Ideal fit signals include: active Google Ads or LSA spend,
                an average booked job above £300, at least 40 inbound calls per month, and
                real after-hours emergency demand.
              </p>
              <p>
                We are a poor fit for brand-new one-truck operators still building demand,
                shops that primarily work general construction with occasional plumbing, or
                businesses looking for the cheapest per-minute answering rate without booking
                workflow. We would rather point you to a better option than sell the wrong
                plan.
              </p>
              <p>
                Still unsure? Email{" "}
                <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a> with your city,
                call volume, and average ticket. Read the full{" "}
                <Link href="/faq">plumbing AI receptionist FAQ</Link>, explore our{" "}
                <Link href="/about">about Owlbell</Link>, or return to the{" "}
                <Link href="/">Owlbell homepage</Link> for the ROI calculator and sample
                workflow.
              </p>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}