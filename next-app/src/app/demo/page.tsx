import type { Metadata } from "next";
import Link from "next/link";
import TrustPage from "@/components/TrustPage";
import { CTA_LAUNCH_AI, CTA_START_TRIAL, onboardingHref } from "@/lib/marketing-cta";

/** Drop the MP3 at public/demos/plumbing-emergency-sample.mp3 to enable playback. */
const DEMO_AUDIO_SRC = "/demos/plumbing-emergency-sample.mp3";

export const metadata: Metadata = {
  title: "Sample Call — Owlbell",
  description:
    "Listen to a real Retell AI plumbing emergency intake — after-hours burst pipe, address captured, emergency flagged, on-call team notified.",
};

export default function DemoPage() {
  return (
    <TrustPage
      title="Sample call"
      meta="Plumbing emergency intake · After hours · Live Retell recording"
    >
      <section>
        <p>
          This is a real call through our Retell AI receptionist — not a voice-over or
          marketing read. Burst pipe, basement flooding, after hours: Morgan qualifies
          the emergency, captures the address, and routes to the on-call team.
        </p>
      </section>

      <section className="demo-player-wrap">
        <div className="demo-player">
          <div className="demo-player-badge">Live recording</div>
          <p className="demo-player-title">Burst pipe · basement flooding · ~11 PM</p>
          <p className="demo-player-desc">
            Rapid Flow Plumbing demo agent (retell-Willa). Same intake structure we
            deploy on customer lines after onboarding.
          </p>

          <audio className="demo-audio" controls preload="metadata">
            <source src={DEMO_AUDIO_SRC} type="audio/mpeg" />
            Your browser does not support embedded audio.
          </audio>
        </div>

        <ul className="demo-callout-list">
          <li>
            <strong>Pickup:</strong> Under 2 seconds — no hold music
          </li>
          <li>
            <strong>Emergency flag:</strong> Active leak, occupant home
          </li>
          <li>
            <strong>Booked:</strong> Next-morning slot with lead tech
          </li>
          <li>
            <strong>Owner alert:</strong> SMS summary + caller number
          </li>
        </ul>
      </section>

      <section>
        <h2>What you are hearing</h2>
        <p>
          Caller reports a burst pipe at 4821 Maple Drive, Denver. Agent Morgan flags it
          as an emergency, confirms Sarah Mitchell&apos;s callback number, and attempts
          on-call transfer. Your shop gets this flow with your business name, service
          area, and pricing guardrails — configured by our team during intake.
        </p>
        <p>
          Questions about recordings, ServiceTitan, or go-live timing? See the{" "}
          <Link href="/faq">FAQ</Link>.
        </p>
      </section>

      <section className="demo-sandbox">
        <h2>Interactive sandbox</h2>
        <p>
          Configure a sample agent in onboarding, then place a test call — no human demo booking required.
        </p>
        <div className="hero-dispatch-actions">
          <Link href={onboardingHref({ source: "demo" })} className="btn btn--copper">
            {CTA_LAUNCH_AI}
          </Link>
          <Link href={onboardingHref({ source: "demo_trial" })} className="btn btn--outline">
            {CTA_START_TRIAL}
          </Link>
        </div>
      </section>
    </TrustPage>
  );
}