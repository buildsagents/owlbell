const BADGES = [
  { label: "TCPA compliant workflows" },
  { label: "GDPR-ready data handling" },
  { label: "Call recording disclosures" },
  { label: "AES-256 at rest" },
] as const;

export function ComplianceBadges() {
  return (
    <div className="compliance-badges" aria-label="Compliance and security">
      {BADGES.map(({ label }) => (
        <span key={label} className="compliance-badge">
          {label}
        </span>
      ))}
    </div>
  );
}

export default ComplianceBadges;