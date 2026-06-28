import type { Metadata } from "next";
import LegalDocument from "@/components/LegalDocument";

export const metadata: Metadata = {
  title: "Privacy Policy — Owlbell",
  description: "How Owlbell collects, uses, and protects customer and caller data.",
};

export default function PrivacyPage() {
  return (
    <LegalDocument title="Privacy Policy" effectiveDate="June 24, 2026">
      <section>
        <h2>1. Who this covers</h2>
        <ul>
          <li>
            <strong>Customers:</strong> the businesses that subscribe to Owlbell.
          </li>
          <li>
            <strong>Callers/End Users:</strong> people who call our Customers&apos; phone
            numbers and interact with the AI.
          </li>
        </ul>
        <p>
          For caller data processed on a Customer&apos;s behalf, the{" "}
          <strong>Customer is the data controller</strong> and Owlbell is the{" "}
          <strong>processor/service provider</strong> (see the DPA).
        </p>
      </section>

      <section>
        <h2>2. Information we collect</h2>
        <p>
          <strong>From Customers:</strong> name, business details, billing contact,
          payment info (via our payment processor), account credentials, configuration
          (greetings, FAQs, routing).
        </p>
        <p>
          <strong>From Callers (on the Customer&apos;s behalf):</strong>
        </p>
        <ul>
          <li>Phone number / caller ID and call metadata (time, duration, outcome).</li>
          <li>
            <strong>Audio recordings</strong> (where recording is enabled) and{" "}
            <strong>transcripts</strong>.
          </li>
          <li>
            Information the caller provides: name, callback number, reason for calling,
            appointment details, and anything they say during the call.
          </li>
        </ul>
        <p>
          <strong>Automatically:</strong> dashboard usage logs, device/browser info, IP
          address, cookies for authentication and analytics.
        </p>
      </section>

      <section>
        <h2>3. How we use information</h2>
        <ul>
          <li>
            Provide the Service: answer calls, transcribe, take messages, book
            appointments, route calls, notify the Customer, and display results in the
            dashboard.
          </li>
          <li>Billing, support, security, fraud prevention, and legal compliance.</li>
          <li>
            Improve the Service, including model and quality improvements using{" "}
            <strong>aggregated and de-identified</strong> data. We do{" "}
            <strong>not sell</strong> personal information.
          </li>
        </ul>
      </section>

      <section>
        <h2>4. AI processing</h2>
        <p>
          Calls are processed by automated speech-to-text, language models, and
          text-to-speech. Depending on configuration this runs on self-hosted/local
          infrastructure we control, and/or on named subprocessors listed in §5. Outputs
          may be imperfect.
        </p>
      </section>

      <section>
        <h2>5. Sharing &amp; subprocessors</h2>
        <p>We share information with:</p>
        <ul>
          <li>
            <strong>Subprocessors</strong> that help run the Service (e.g., telephony/SIP
            provider, cloud hosting provider, email/SMS provider, payment processor).
          </li>
          <li>
            <strong>Integrations you enable</strong> (e.g., Google Calendar, your CRM) —
            data flows as you configure.
          </li>
          <li>
            <strong>Legal/safety:</strong> when required by law or to protect rights and
            safety.
          </li>
          <li>
            <strong>Business transfers:</strong> in a merger or acquisition, subject to
            this policy.
          </li>
        </ul>
      </section>

      <section>
        <h2>6. Call recording &amp; consent</h2>
        <p>
          Where recording/transcription is enabled, recording laws vary by jurisdiction
          (one-party vs. all-party consent). <strong>Customers are responsible</strong>{" "}
          for ensuring lawful disclosure and consent; Owlbell provides configurable
          recording disclosures.
        </p>
      </section>

      <section>
        <h2>7. Data retention</h2>
        <ul>
          <li>
            Recordings &amp; transcripts: retained for 90 days by default, then deleted,
            unless the Customer configures a different period or law requires longer.
          </li>
          <li>
            Messages, appointments, analytics: for the life of the account plus 30 days.
          </li>
          <li>Billing records: as required by law (typically 7 years).</li>
        </ul>
        <p>Customers can request export or deletion (see §9).</p>
      </section>

      <section>
        <h2>8. Security</h2>
        <p>
          We use reasonable technical and organizational measures: encryption in transit
          (and at rest where supported), access controls, audit logging, and
          least-privilege access. No system is perfectly secure.
        </p>
      </section>

      <section>
        <h2>9. Your rights &amp; choices</h2>
        <p>
          Depending on your location (e.g., CCPA/CPRA, GDPR), you may have rights to
          access, correct, delete, port, or restrict your personal information, and to
          opt out of certain processing. Contact{" "}
          <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a>.
        </p>
        <ul>
          <li>
            <strong>Marketing email:</strong> every message includes an unsubscribe link.
          </li>
          <li>
            <strong>Cookies:</strong> you can control cookies via your browser; some are
            required for login.
          </li>
        </ul>
      </section>

      <section>
        <h2>10. Children</h2>
        <p>
          The Service is not directed to children under 13 and we do not knowingly collect
          their data.
        </p>
      </section>

      <section>
        <h2>11. International transfers</h2>
        <p>
          If data is transferred across borders, we use appropriate safeguards (e.g., SCCs)
          where required.
        </p>
      </section>

      <section>
        <h2>12. Changes</h2>
        <p>
          We may update this policy; material changes will be posted with a new effective
          date and, where required, notified to Customers.
        </p>
      </section>

      <section>
        <h2>13. Contact</h2>
        <p>
          <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a> · Owlbell
        </p>
      </section>
    </LegalDocument>
  );
}