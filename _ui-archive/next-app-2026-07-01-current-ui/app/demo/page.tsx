import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";
import { auditHref } from "@/lib/marketing-cta";
import {
  DEMO_AUDIO_SRC,
  DEMO_CALL_SUMMARY,
  DEMO_PAGE_CTA,
  DEMO_TRANSCRIPT,
  PROOF_DISCLAIMER,
} from "@/lib/demo-call-data";
import DemoPageClient from "./DemoPageClient";

export const metadata: Metadata = {
  title: "Live Retell Demo - Plumbing Emergency Intake | Owlbell",
  description:
    "Talk to Owlbell's live Retell receptionist demo for an after-hours plumbing emergency intake flow.",
};

const SUMMARY_FIELDS = [
  { key: "callerIssue", label: "Caller issue" },
  { key: "urgency", label: "Urgency" },
  { key: "addressCaptured", label: "Address captured" },
  { key: "bookedSlot", label: "Booked slot" },
  { key: "ownerSms", label: "Owner SMS" },
] as const;

export default function DemoPage() {
  return (
    <div className="site">
      <SiteHeader />

      <main className="site-main">
        <section className="demo-hero" id="demo">
          <div className="wrap">
            <header className="demo-hero-head">
              <p className="kicker kicker--dark">Live Retell demo</p>
              <h1>Talk to the receptionist we configure for client lines</h1>
              <p className="demo-hero-lead">
                Start a browser call and speak to the Retell-powered demo agent. It handles a
                burst-pipe intake, captures the job details, and keeps the conversation steady.
              </p>
              <p className="proof-disclaimer">{PROOF_DISCLAIMER}</p>
            </header>

            <div className="demo-live-panel">
              <Suspense fallback={<p className="ob-muted">Loading live demo...</p>}>
                <DemoPageClient />
              </Suspense>
            </div>

            <div className="demo-hero-grid">
              <div className="demo-player">
                <div className="demo-player-badge">Fallback script</div>
                <p className="demo-player-title">Burst pipe - active leak - after hours</p>
                <p className="demo-player-desc">
                  Use this only if your browser blocks microphone access. The live Retell call
                  above is the primary demo.
                </p>
                <audio className="demo-audio" controls preload="metadata">
                  <source src={DEMO_AUDIO_SRC} type="audio/mpeg" />
                  Your browser does not support embedded audio.
                </audio>
              </div>

              <div className="demo-transcript-panel" aria-label="Call transcript">
                <p className="demo-transcript-label">Transcript</p>
                <ol className="demo-transcript">
                  {DEMO_TRANSCRIPT.map((line, index) => (
                    <li key={index} className={`demo-transcript-line demo-transcript-line--${line.role}`}>
                      <span className="demo-transcript-role">
                        {line.role === "agent" ? "Agent" : "Caller"}
                      </span>
                      <p>{line.text}</p>
                    </li>
                  ))}
                </ol>
              </div>
            </div>

            <div className="demo-summary-row">
              <article className="demo-summary-card">
                <p className="kicker kicker--dark">Call summary</p>
                <h2>What Owlbell captured on this call</h2>
                <dl className="demo-summary-dl">
                  {SUMMARY_FIELDS.map(({ key, label }) => (
                    <div key={key}>
                      <dt>{label}</dt>
                      <dd>{DEMO_CALL_SUMMARY[key]}</dd>
                    </div>
                  ))}
                </dl>
              </article>

              <div className="demo-cta-block">
                <p>Forward missed calls to Owlbell. We qualify emergencies, route urgent work, and text your team the details.</p>
                <Link href={auditHref({ source: "demo" })} className="btn btn--primary btn--block">
                  {DEMO_PAGE_CTA}
                </Link>
                <Link href="/faq" className="demo-cta-secondary">
                  Questions about recordings or setup? Read the FAQ
                </Link>
              </div>
            </div>
          </div>
        </section>

      </main>

      <SiteFooter />
    </div>
  );
}
