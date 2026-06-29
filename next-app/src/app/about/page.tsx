import type { Metadata } from "next";
import Link from "next/link";
import TrustPage from "@/components/TrustPage";
import { CTA_LAUNCH_AI, onboardingHref } from "@/lib/marketing-cta";

export const metadata: Metadata = {
  title: "About — Owlbell",
  description:
    "Owlbell is a self-serve AI receptionist for US service businesses. Configure voice, scripts, and routing in under 15 minutes — with human support when you need it.",
};

export default function AboutPage() {
  return (
    <TrustPage
      title="About Owlbell"
      meta="AI receptionist for US service businesses · Self-serve setup · Human support on demand"
    >
      <section>
        <h2>What we are</h2>
        <p>
          Owlbell is a <strong>self-serve AI receptionist</strong> built for plumbing,
          HVAC, electrical, dental, legal, and other appointment-driven service businesses.
          You configure voice, scripts, hours, and integrations in onboarding — then go live
          with a first test call in under 15 minutes.
        </p>
        <p>
          We are not a generic call center and not a blank DIY bot. Owlbell is optimized for
          emergency intake, booking, and owner alerts — the moments that cost you revenue when
          voicemail picks up.
        </p>
      </section>

      <section>
        <h2>Who is behind it</h2>
        <p>
          Owlbell is run by a small US-based team: product engineers, onboarding guides,
          and customer success. There is no founder face or voice on the homepage because this
          is a <strong>product service</strong>, not a personal brand play.
        </p>
        <p>
          Questions go to{" "}
          <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a>. We reply within a few
          hours on business days. Chat and email support are included on every plan; live
          chat escalation is available on Growth and Scale tiers.
        </p>
      </section>

      <section>
        <h2>Self-serve first — humans when you need them</h2>
        <p>
          Most owners complete onboarding without a call: business details, phone routing,
          AI personality, knowledge base, calendar/CRM preferences, and plan selection. Your
          progress saves to this device and the cloud so you can resume on any screen.
        </p>
        <p>
          Inbound calls from <em>your customers</em> are answered 24/7. That is the product.
          Owlbell support stays async (email/chat) unless you request a review session.
        </p>
      </section>

      <section>
        <h2>Vertical focus — on purpose</h2>
        <p>
          We ship vertical-specific landing pages and default scripts because emergency
          patterns, pricing guardrails, and dispatch logic differ by trade. Narrow defaults
          mean faster activation and fewer &ldquo;the AI said what?&rdquo; moments.
        </p>
        <ul>
          <li>Service areas and zip boundaries configured to your shop</li>
          <li>Emergency triggers tuned per vertical (burst pipes, no heat, after-hours dental, etc.)</li>
          <li>Trip charges and quote guardrails — your numbers, not generic defaults</li>
          <li>Handoff to ServiceTitan, Jobber, Housecall Pro, or plain SMS summaries</li>
        </ul>
      </section>

      <section>
        <h2>How activation works</h2>
        <ol>
          <li>
            <strong>Minutes 0–10:</strong> Complete the 7-step onboarding wizard — voice, KB,
            calendar, CRM, and plan.
          </li>
          <li>
            <strong>Minute 10:</strong> Owlbell provisions your inbound AI line (Retell when
            configured, or sandbox for instant testing).
          </li>
          <li>
            <strong>Minute 15:</strong> Place your first test call from the confirmation screen
            and open your dashboard.
          </li>
        </ol>
        <p>
          Script tuning continues in the dashboard — update greetings, FAQs, and routing rules
          anytime with version history.
        </p>
      </section>

      <section>
        <h2>AI answers the calls</h2>
        <p>
          Callers hear a natural receptionist trained on <em>your</em> shop. Behind that is
          AI optimized for service intake: fast pickup (under two seconds), structured data
          capture, and owner SMS summaries with estimated job value when available.
        </p>
        <p>
          Recordings and transcripts live in your dashboard. Disclosure language is configured
          for your state&apos;s recording rules. See our{" "}
          <Link href="/privacy">Privacy Policy</Link> for data handling.
        </p>
      </section>

      <section>
        <h2>Process transparency</h2>
        <p>Nothing hidden behind &ldquo;contact sales&rdquo;:</p>
        <ul>
          <li>
            <strong>Pricing:</strong> Launch $1,497/mo · Growth $4,997/mo · Scale $9,997+/mo —
            selectable in onboarding
          </li>
          <li>
            <strong>Trial:</strong> 7 days, cancel before day seven to skip the first monthly
            charge
          </li>
          <li>
            <strong>Workflow:</strong>{" "}
            <Link href="/how-it-works">How it works</Link> — answer, qualify, book, notify
          </li>
          <li>
            <strong>Sample:</strong>{" "}
            <Link href="/demo">Try the demo sandbox</Link>
          </li>
          <li>
            <strong>Questions:</strong> <Link href="/faq">Searchable FAQ</Link> covers
            integrations, recordings, after-hours, and more
          </li>
        </ul>
      </section>

      <section>
        <h2>Ready to launch your AI receptionist?</h2>
        <p>
          Start a 7-day trial in onboarding or email us first — whatever fits how you buy
          services for your shop.
        </p>
        <p>
          <Link href={onboardingHref({ source: "about" })} className="btn btn--copper">
            {CTA_LAUNCH_AI}
          </Link>{" "}
          <Link href="/#pricing" className="btn btn--outline">
            View plans
          </Link>
        </p>
      </section>
    </TrustPage>
  );
}