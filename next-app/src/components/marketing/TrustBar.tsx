const TRUST_STATS = [
  { label: "50+ service businesses" },
  { label: "4.9★ avg owner rating" },
  { label: "TCPA-aware · encrypted" },
] as const;

const LOGOS = ["Summit HVAC", "Bright Smile Dental", "Lakeside Legal", "ProFlow Plumbing", "Volt Electric"];

export function TrustBar() {
  return (
    <section className="section section--warm trust-bar" aria-label="Trust signals">
      <div className="wrap">
        <div className="trust-bar-stats">
          {TRUST_STATS.map(({ label }) => (
            <span key={label} className="trust-bar-stat">
              {label}
            </span>
          ))}
        </div>
        <div className="trust-bar-logos">
          {LOGOS.map((name) => (
            <span key={name} className="trust-bar-logo">
              {name}
            </span>
          ))}
        </div>
        <p className="trust-bar-case">
          Case snapshot: ProFlow Plumbing recovered <strong>$18.4k</strong> in 90 days from
          after-hours bookings.
        </p>
      </div>
    </section>
  );
}

export default TrustBar;