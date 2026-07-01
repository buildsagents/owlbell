const TRUST_ITEMS = [
  { value: "UK-based", label: "Registered company" },
  { value: "PECR", label: "Compliant call handling" },
  { value: "GDPR", label: "Data protection" },
  { value: "CTPS", label: "Outbound screening" },
];

export default function TrustSection() {
  return (
    <section className="section section--alt" style={{ padding: "32px 0" }}>
      <div className="wrap">
        <div className="trust-row">
          {TRUST_ITEMS.map((item) => (
            <div key={item.value} className="trust-item">
              <div className="trust-value">{item.value}</div>
              <span className="trust-label">{item.label}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
