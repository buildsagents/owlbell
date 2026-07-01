import Link from "next/link";

export default function SolutionSection() {
  return (
    <section className="section section--alt" id="solution">
      <div className="wrap">
        <div className="grid-2">
          <div>
            <span className="section-label">The solution</span>
            <h2>Your clients hear a receptionist, not a bot.</h2>
            <p style={{ color: "var(--gray-500)", lineHeight: "1.7", marginTop: "16px" }}>
              Owlbell works like a trained after-hours receptionist. The voice flow opens naturally,
              asks one question at a time, confirms details, handles urgent safety context, and only
              escalates when the call rules say to escalate.
            </p>
            <p style={{ color: "var(--gray-500)", lineHeight: "1.7", marginTop: "16px" }}>
              The client does not need to write prompts or learn software. We configure, test, and
              tune the receptionist until it matches their business.
            </p>
            <div style={{ marginTop: "24px" }}>
              <Link href="/onboarding?source=solution" className="btn btn--primary">
                Book a Demo
              </Link>
            </div>
          </div>
          <div className="card card--plain" style={{ padding: "32px", border: "1px solid var(--gray-200)", background: "var(--white)" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                <div style={{ width: "24px", height: "24px", borderRadius: "50%", background: "var(--blue-light)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: "0.75rem", color: "var(--blue)", fontWeight: "700" }}>1</div>
                <div>
                  <div style={{ fontWeight: "600", marginBottom: "4px" }}>Call comes in</div>
                  <p className="text-sm" style={{ color: "var(--gray-500)", margin: 0 }}>After-hours overflow forwarded to Owlbell. The caller gets a calm receptionist immediately.</p>
                </div>
              </div>
              <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                <div style={{ width: "24px", height: "24px", borderRadius: "50%", background: "var(--blue-light)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: "0.75rem", color: "var(--blue)", fontWeight: "700" }}>2</div>
                <div>
                  <div style={{ fontWeight: "600", marginBottom: "4px" }}>Details are captured cleanly</div>
                  <p className="text-sm" style={{ color: "var(--gray-500)", margin: 0 }}>Urgency, address, callback, safety context, and job type are confirmed without robotic loops.</p>
                </div>
              </div>
              <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                <div style={{ width: "24px", height: "24px", borderRadius: "50%", background: "var(--blue-light)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: "0.75rem", color: "var(--blue)", fontWeight: "700" }}>3</div>
                <div>
                  <div style={{ fontWeight: "600", marginBottom: "4px" }}>SMS lands on the owner&apos;s phone</div>
                  <p className="text-sm" style={{ color: "var(--gray-500)", margin: 0 }}>Emergency - burst pipe - Sarah M. - active water - callback on file.</p>
                </div>
              </div>
              <div style={{ display: "flex", gap: "12px", alignItems: "flex-start" }}>
                <div style={{ width: "24px", height: "24px", borderRadius: "50%", background: "var(--blue-light)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: "0.75rem", color: "var(--blue)", fontWeight: "700" }}>4</div>
                <div>
                  <div style={{ fontWeight: "600", marginBottom: "4px" }}>The call flow gets better weekly</div>
                  <p className="text-sm" style={{ color: "var(--gray-500)", margin: 0 }}>We review outcomes and tune prompts, routing, and handoffs for more booked work.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
