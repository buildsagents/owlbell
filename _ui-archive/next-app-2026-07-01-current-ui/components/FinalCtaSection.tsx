import Link from "next/link";

export default function FinalCtaSection() {
  return (
    <section className="section section--dark" id="get-started">
      <div className="wrap final-cta-inner">
        <h2>Launch a receptionist clients can trust.</h2>
        <p>
          Forward overflow calls to Owlbell. We answer, qualify, route, and text the job
          details. Managed setup and tuning included, so the client is not left with a raw AI bot.
        </p>
        <div className="final-cta-actions">
          <Link href="/onboarding?source=final_cta" className="btn btn--secondary btn--lg">
            Book a Demo
          </Link>
          <Link href="/demo" className="btn btn--ghost btn--lg" style={{ color: "var(--gray-400)" }}>
            Hear Demo Flow
          </Link>
        </div>
      </div>
    </section>
  );
}
