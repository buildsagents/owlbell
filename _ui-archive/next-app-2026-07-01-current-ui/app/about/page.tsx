import type { Metadata } from "next";
import Link from "next/link";
import TrustPage from "@/components/TrustPage";
import { TRUST_FAQ_ITEMS } from "@/lib/faq-data";
import { CTA_PRIMARY, CTA_SECONDARY, auditHref, sampleCallHref } from "@/lib/marketing-cta";

export const metadata: Metadata = {
  title: "About - Owlbell",
  description:
    "Owlbell is a real UK agency. Managed AI receptionist for plumbing shops - we set it up, you forward missed calls, we tune the script. Straight answers on AI mistakes, recordings, integrations, and cancellation.",
};

export default function AboutPage() {
  return (
    <TrustPage
      title="About Owlbell"
      meta="A real company - Managed setup - Straight answers before you sign up"
    >
      <section>
        <h2>What we are</h2>
        <p>
          Owlbell is a <strong>managed AI receptionist</strong> built for plumbing,
          drain, sewer, and water-heater companies. We configure voice, emergency scripts,
          hours, service areas, and integrations - you forward missed calls and get booked
          jobs by SMS.
        </p>
        <p>
          We are not a generic call center and not a DIY bot you have to train yourself.
          Owlbell is optimized for emergency intake, booking, and owner alerts - the moments
          that cost plumbing shops revenue when voicemail picks up.
        </p>
      </section>

      <section>
        <h2>Is this a real company?</h2>
        <p>
          Yes. Owlbell is a UK-based product company serving plumbing shops across England, Scotland, and Wales.
          We publish pricing on the site, offer a{" "}
          <Link href={auditHref({ source: "about" })}>free missed-call audit</Link> before
          you pay anything, and reply from{" "}
          <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a> on business days.
          Privacy Policy and Terms are in the footer. You can{" "}
          <Link href={sampleCallHref()}>hear a real sample call</Link> and review
          anonymized results on the homepage before committing.
        </p>
      </section>

      <section className="about-trust-faq">
        <h2>What owners ask before they sign up</h2>
        <p className="about-trust-lead">
          Eight questions we hear on every sales call - answered here so you do not have to
          guess.
        </p>
        <dl className="about-trust-dl">
          {TRUST_FAQ_ITEMS.map((item) => (
            <div key={item.id} id={item.id}>
              <dt>
                <Link href={`/faq#${item.id}`}>{item.question}</Link>
              </dt>
              <dd>{item.answer}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section>
        <h2>Who sets this up?</h2>
        <p>
          <strong>We do</strong> - not you. You share how your shop runs via a short audit
          form: business name, service area, main phone, missed-call volume, and emergency
          coverage. Our team configures voice, scripts, calendar handoff, and forwarding.
          You forward missed calls - we tune the script from real conversations during your
          trial.
        </p>
        <p>
          Inbound calls from <em>your plumbing customers</em> are answered 24/7. That is the
          product. Owlbell support stays async (email/chat) unless you request a review
          session.
        </p>
      </section>

      <section>
        <h2>Vertical focus - on purpose</h2>
        <p>
          We focus on plumbing because emergency patterns, pricing guardrails, and dispatch
          logic are specific. Narrow defaults mean faster go-live and fewer awkward call
          moments.
        </p>
        <ul>
          <li>Service areas and zip boundaries configured to your shop</li>
          <li>Emergency triggers tuned for burst pipes, sewage backups, active leaks, and no-hot-water calls</li>
          <li>Trip charges and quote guardrails - your numbers, not generic defaults</li>
          <li>Handoff to ServiceTitan, Jobber, Housecall Pro, or plain SMS summaries</li>
        </ul>
      </section>

      <section>
        <h2>How you get started</h2>
        <ol>
          <li>
            <strong>Day 0:</strong> Submit the{" "}
            <Link href={auditHref({ source: "about" })}>free missed-call audit</Link> - two
            minutes, no billing or voice config required.
          </li>
          <li>
            <strong>Days 1-3:</strong> We send your recovery audit and sample script. Our team
            configures voice, emergency rules, and forwarding on your line.
          </li>
          <li>
            <strong>Day 3+:</strong> You forward missed calls. We tune from real conversations.
            You get booked jobs by SMS.
          </li>
        </ol>
      </section>

      <section>
        <h2>Process transparency</h2>
        <p>Nothing hidden behind contact sales:</p>
        <ul>
          <li>
            <strong>Pricing:</strong> Launch £1,197/mo - Growth £3,997/mo - Scale £7,997+/mo
          </li>
          <li>
            <strong>Trial:</strong> 7 days, cancel before day seven - no monthly charge
          </li>
          <li>
            <strong>Workflow:</strong>{" "}
            <Link href="/how-it-works">How it works</Link> - answer, qualify, book, notify
          </li>
          <li>
            <strong>Sample:</strong>{" "}
            <Link href={sampleCallHref()}>{CTA_SECONDARY}</Link>
          </li>
          <li>
            <strong>All questions:</strong> <Link href="/faq">Searchable FAQ</Link>
          </li>
        </ul>
      </section>

      <section>
        <h2>See how many calls you&apos;re missing</h2>
        <p>
          Get a free missed-call audit - we model what after-hours voicemail is costing your
          shop before you commit.
        </p>
        <p>
          <Link href={auditHref({ source: "about" })} className="btn btn--copper">
            {CTA_PRIMARY}
          </Link>{" "}
          <Link href={sampleCallHref()} className="btn btn--outline">
            {CTA_SECONDARY}
          </Link>
        </p>
      </section>
    </TrustPage>
  );
}
