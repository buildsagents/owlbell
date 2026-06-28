import type { Metadata } from "next";
import Link from "next/link";
import TrustPage from "@/components/TrustPage";

export const metadata: Metadata = {
  title: "About — Owlbell",
  description:
    "Owlbell is a US-based managed reception agency for plumbing contractors. Human-led onboarding, AI-powered answering, full process transparency.",
};

export default function AboutPage() {
  return (
    <TrustPage
      title="About Owlbell"
      meta="Managed reception for US plumbing contractors · Human-led setup · AI answers every call"
    >
      <section>
        <h2>What we are</h2>
        <p>
          Owlbell is a <strong>managed reception agency</strong> — not a DIY phone bot
          you configure on a Saturday. We answer, qualify, book, and text your team the
          job details. Plumbing contractors only. US-based operations team.
        </p>
        <p>
          You do not hire us to learn another dashboard. You hire us so every emergency
          call gets answered before voicemail — nights, weekends, and lunch rush included.
        </p>
      </section>

      <section>
        <h2>Who is behind it</h2>
        <p>
          Owlbell is run by a small US-based agency team: onboarding specialists,
          script writers, and customer success — people who have set up call workflows
          for home-service businesses. There is no founder face or voice on the
          homepage because this is an <strong>agency service</strong>, not a personal
          brand play.
        </p>
        <p>
          Questions go to{" "}
          <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a>. We reply within a
          few hours on business days.
        </p>
      </section>

      <section>
        <h2>Plumbing only — on purpose</h2>
        <p>
          We do not answer for HVAC, roofing, or law firms. Plumbing has predictable
          emergency patterns, pricing guardrails, and dispatch logic. Narrow focus means
          better scripts, faster onboarding, and fewer &ldquo;the AI said what?&rdquo;
          moments.
        </p>
        <ul>
          <li>Service areas and zip boundaries configured to your shop</li>
          <li>Emergency triggers: burst pipes, active leaks, no water, sewer backup</li>
          <li>Trip charges and quote guardrails — your numbers, not generic defaults</li>
          <li>Handoff to ServiceTitan, Jobber, Housecall Pro, or plain SMS summaries</li>
        </ul>
      </section>

      <section>
        <h2>Human-led onboarding</h2>
        <p>
          Software-first tools hand you a blank script. We do the opposite:
        </p>
        <ol>
          <li>
            <strong>Day 0:</strong> Subscribe and complete intake — services, areas,
            pricing bounds, on-call rules.
          </li>
          <li>
            <strong>Day 1:</strong> Your specialist builds scripts, calendar rules, and
            emergency routing.
          </li>
          <li>
            <strong>Day 2:</strong> Test calls, forward your line, go live.
          </li>
        </ol>
        <p>
          Script tuning is included — plumbing has edge cases, and we treat updates as
          operations, not a support ticket.
        </p>
      </section>

      <section>
        <h2>AI answers the calls</h2>
        <p>
          Callers hear a natural receptionist trained on <em>your</em> shop. Behind
          that is AI optimized for plumbing intake: fast pickup (under two seconds),
          structured data capture, and owner SMS summaries with estimated job value.
        </p>
        <p>
          Recordings and transcripts live in your dashboard. Disclosure language is
          configured for your state&apos;s recording rules. See our{" "}
          <Link href="/privacy">Privacy Policy</Link> for data handling.
        </p>
      </section>

      <section>
        <h2>Process transparency</h2>
        <p>Nothing hidden behind &ldquo;contact sales&rdquo;:</p>
        <ul>
          <li>
            <strong>Pricing:</strong> Launch $1,497/mo · Growth $4,997/mo — shown
            before checkout
          </li>
          <li>
            <strong>Trial:</strong> 7 days, cancel before day seven to skip the first
            monthly charge
          </li>
          <li>
            <strong>Workflow:</strong>{" "}
            <Link href="/#how">Three steps on every call</Link> — answer, book, text
          </li>
          <li>
            <strong>Sample:</strong>{" "}
            <Link href="/demo">Listen to a plumbing emergency intake</Link>
          </li>
          <li>
            <strong>Questions:</strong> <Link href="/faq">FAQ</Link> covers
            ServiceTitan, recordings, after-hours, and more
          </li>
        </ul>
      </section>

      <section>
        <h2>Ready to try it on your line?</h2>
        <p>
          Start a 7-day trial or email us first — whatever fits how you buy services
          for your shop.
        </p>
        <p>
          <Link href="/#pricing" className="btn btn--copper">
            View plans
          </Link>
        </p>
      </section>
    </TrustPage>
  );
}