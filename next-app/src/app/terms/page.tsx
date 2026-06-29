import type { Metadata } from "next";
import LegalDocument from "@/components/LegalDocument";

export const metadata: Metadata = {
  title: "Terms of Service — Owlbell",
  description: "Terms governing use of the Owlbell self-serve AI receptionist for service businesses.",
};

export default function TermsPage() {
  return (
    <LegalDocument title="Terms of Service" effectiveDate="June 24, 2026">
      <section>
        <h2>1. Agreement</h2>
        <p>
          By signing an order form, clicking &quot;I agree,&quot; or using the Service,
          you (&quot;Customer&quot;) agree to these Terms. If you use the Service on
          behalf of a business, you represent that you are authorized to bind it.
        </p>
      </section>

      <section>
        <h2>2. The Service</h2>
        <p>
          Owlbell provides a managed, AI-powered phone answering service that may,
          depending on your plan: answer inbound calls, conduct automated conversations,
          take messages, book appointments, route or transfer calls, transcribe and (where
          enabled) record calls, send notifications, and provide a web dashboard and
          analytics. Features by tier are described at{" "}
          <a href="/#pricing">owlbell.xyz/#pricing</a>.
        </p>
      </section>

      <section>
        <h2>3. Customer Responsibilities</h2>
        <p>You are responsible for:</p>
        <ul>
          <li>
            the accuracy of the business information, greetings, scripts, FAQs, and routing
            rules you provide;
          </li>
          <li>
            obtaining all <strong>consents and disclosures</strong> required to record,
            transcribe, and process calls and caller data in every jurisdiction where your
            callers are located;
          </li>
          <li>
            your compliance with laws applicable to your business, including TCPA,
            CAN-SPAM, DNC rules, and any industry rules;
          </li>
          <li>
            using the Service only for lawful purposes and not for emergency services
            (911), robocalling, harassment, or deceptive practices.
          </li>
        </ul>
      </section>

      <section>
        <h2>4. Acceptable Use</h2>
        <p>
          You will not, and will not permit others to: resell or white-label the Service
          except under a written partner agreement; reverse engineer the Service; use it to
          place unlawful outbound calls/SMS; transmit malware; or interfere with the
          Service&apos;s operation or other customers.
        </p>
      </section>

      <section>
        <h2>5. Fees, Billing &amp; Taxes</h2>
        <ul>
          <li>
            Fees are set out on your order form / plan. Plans are billed{" "}
            <strong>monthly or annually in advance</strong>; usage overages and add-ons
            are billed in arrears.
          </li>
          <li>
            A one-time <strong>setup fee</strong> may apply and is non-refundable once
            onboarding begins.
          </li>
          <li>
            Payment is due on the invoice date (NET 0). <strong>Late or failed payments</strong>{" "}
            may result in suspension after 10 days&apos; notice.
          </li>
          <li>Fees are exclusive of taxes; you are responsible for applicable taxes.</li>
          <li>We may change prices on 30 days&apos; notice effective at your next renewal.</li>
        </ul>
      </section>

      <section>
        <h2>6. Price Lock</h2>
        <p>
          Customers on annual billing are guaranteed the same monthly rate for the full
          term. Any price increase will only apply at renewal with 30 days&apos; notice.
        </p>
      </section>

      <section>
        <h2>7. Term, Renewal &amp; Cancellation</h2>
        <ul>
          <li>Month-to-month plans renew monthly until cancelled with 30 days&apos; notice.</li>
          <li>Annual plans renew automatically unless cancelled 30 days before renewal.</li>
          <li>
            We may suspend or terminate for material breach not cured within 10 days of
            notice.
          </li>
          <li>
            On termination, your access ends; we will make your data available for export
            for 30 days, after which it may be deleted.
          </li>
        </ul>
      </section>

      <section id="guarantee">
        <h2>8. Booking Guarantee (Growth &amp; Scale)</h2>
        <p>
          For Growth and Scale plans, if Owlbell does not book at least five (5) qualified
          jobs within the first thirty (30) days after go-live, we will continue script
          tuning, routing optimization, and success-team support at no additional charge
          until five jobs are booked — provided that:
        </p>
        <ul>
          <li>Call forwarding to Owlbell is active and tested;</li>
          <li>You complete onboarding and approve scripts within 5 business days;</li>
          <li>Your business receives at least 40 inbound calls per month; and</li>
          <li>You remain current on subscription fees.</li>
        </ul>
        <p>
          This guarantee does not apply to Launch plans, paused accounts, or businesses
          outside plumbing trades. Owlbell does not guarantee specific revenue outcomes.
        </p>
      </section>

      <section>
        <h2>9. Service Levels &amp; Availability</h2>
        <p>
          We target high availability but, except where a signed SLA applies, the Service
          is provided <strong>&quot;as available.&quot;</strong> AI systems are
          probabilistic and may make mistakes. The Service is <strong>not</strong> a
          substitute for emergency services.
        </p>
      </section>

      <section>
        <h2>10. AI Disclaimer</h2>
        <p>
          The Service uses automated speech recognition and language models. Transcriptions,
          bookings, summaries, and routing may contain errors. You are responsible for
          reviewing captured messages and confirming appointments. We do not guarantee any
          specific call outcome, booking rate, or revenue result.
        </p>
      </section>

      <section>
        <h2>11–17. Legal</h2>
        <p>
          Intellectual property, confidentiality, warranties, limitation of liability,
          indemnification, governing law (Delaware, USA), changes, and miscellaneous terms
          apply as described in the full agreement. Questions:{" "}
          <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a>.
        </p>
        <p>
          See also our <a href="/privacy">Privacy Policy</a>.
        </p>
      </section>
    </LegalDocument>
  );
}