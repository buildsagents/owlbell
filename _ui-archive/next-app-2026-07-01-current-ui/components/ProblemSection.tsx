export default function ProblemSection() {
  return (
    <section className="section" id="problem">
      <div className="wrap">
        <div className="section-lead">
          <span className="section-label">The problem</span>
          <h2>After hours, every missed call is lost revenue.</h2>
          <p>
            Plumbing emergencies don&apos;t happen during business hours. Burst pipes, blocked drains,
            and gas leaks call at night - when your team is off and your phone goes to voicemail.
          </p>
        </div>
        <div className="grid-3" style={{ textAlign: "center" }}>
          <div>
            <div style={{ fontSize: "2.5rem", fontWeight: "700", letterSpacing: "-0.03em", marginBottom: "8px" }}>
              71%
            </div>
            <p className="text-sm" style={{ color: "var(--gray-500)", margin: 0 }}>
              of plumbing calls after 6 PM go to voicemail
            </p>
          </div>
          <div>
            <div style={{ fontSize: "2.5rem", fontWeight: "700", letterSpacing: "-0.03em", marginBottom: "8px" }}>
              3x
            </div>
            <p className="text-sm" style={{ color: "var(--gray-500)", margin: 0 }}>
              more likely to call the next listing if unanswered
            </p>
          </div>
          <div>
            <div style={{ fontSize: "2.5rem", fontWeight: "700", letterSpacing: "-0.03em", marginBottom: "8px" }}>
              &pound;18k+
            </div>
            <p className="text-sm" style={{ color: "var(--gray-500)", margin: 0 }}>
              recovered per quarter from overflow capture
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
