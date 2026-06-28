import Link from "next/link";

export default function SampleCallSection() {
  return (
    <section className="section sample-call" id="sample-call">
      <div className="wrap sample-call-grid">
        <div className="sample-call-copy">
          <p className="kicker kicker--dark">Hear it yourself</p>
          <h2>Listen to a sample call</h2>
          <p>
            A real plumbing emergency intake — burst pipe, after hours, booked for
            morning dispatch. No actor, no founder voice-over. Just how Owlbell sounds
            on your line.
          </p>
          <Link href="/demo" className="btn btn--copper">
            Play sample call
          </Link>
        </div>

        <div className="sample-call-card" aria-hidden="true">
          <div className="sample-call-wave">
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
          </div>
          <p className="sample-call-label">Emergency intake · After hours</p>
          <p className="sample-call-duration num">~2:40</p>
        </div>
      </div>
    </section>
  );
}