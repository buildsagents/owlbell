import type { Metadata } from "next";
import Link from "next/link";
import TrustPage from "@/components/TrustPage";

/** Drop the MP3 at public/demos/plumbing-emergency-sample.mp3 to enable playback. */
const DEMO_AUDIO_SRC = "/demos/plumbing-emergency-sample.mp3";

export const metadata: Metadata = {
  title: "Sample Call — Owlbell",
  description:
    "Listen to a sample plumbing emergency intake call — after-hours burst pipe, qualified and booked for morning dispatch.",
};

export default function DemoPage() {
  return (
    <TrustPage
      title="Sample call"
      meta="Plumbing emergency intake · After hours · Composite recording"
    >
      <section>
        <p>
          This is what callers experience when your line forwards to Owlbell: fast
          pickup, emergency qualification, address capture, and a booked window for
          dispatch. The full recording is publishing shortly.
        </p>
      </section>

      <section className="demo-player-wrap">
        <div className="demo-player">
          <div className="demo-player-badge">Coming soon</div>
          <p className="demo-player-title">Burst pipe · basement flooding · 11:04 PM</p>
          <p className="demo-player-desc">
            Real intake flow — not a scripted marketing read. Same structure we deploy
            on customer lines after onboarding.
          </p>

          <audio className="demo-audio" controls preload="none">
            <source src={DEMO_AUDIO_SRC} type="audio/mpeg" />
            Your browser does not support embedded audio.
          </audio>

          <p className="demo-player-note">
            Audio file path: <code>public/demos/plumbing-emergency-sample.mp3</code>
          </p>
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
          A composite example based on common after-hours plumbing emergencies. Your
          scripts, voice, service area, and pricing guardrails are configured by our
          team — this sample shows the <em>flow</em>, not your exact wording.
        </p>
        <p>
          Questions about recordings, ServiceTitan, or go-live timing? See the{" "}
          <Link href="/faq">FAQ</Link>.
        </p>
      </section>

      <section>
        <p>
          <Link href="/#pricing" className="btn btn--copper">
            Start 7-day trial
          </Link>
        </p>
      </section>
    </TrustPage>
  );
}