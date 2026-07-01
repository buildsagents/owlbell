const PROOF_METRICS = [
  { value: "1.8s", label: "Avg answer", detail: "Burst pipe call" },
  { value: "0", label: "Voicemail / wk", detail: "After go-live" },
  { value: "£850", label: "Booked emergency", detail: "Same-night intake" },
  { value: "24/7", label: "Coverage", detail: "Overflow + after hours" },
] as const;

export function TrustBar() {
  return (
    <section className="ops-metrics-bar" aria-label="Operational proof metrics">
      <div className="wrap">
        <dl className="ops-metrics-grid">
          {PROOF_METRICS.map(({ value, label, detail }) => (
            <div key={label} className="ops-metric">
              <dd className="num ops-metric-value">{value}</dd>
              <dt className="ops-metric-label">{label}</dt>
              <span className="ops-metric-detail">{detail}</span>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

export default TrustBar;