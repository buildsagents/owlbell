import Link from "next/link";
import { onboardingHref } from "@/lib/marketing-cta";

const MAGNETS = [
  {
    title: "Free missed-call audit",
    description: "Estimate volume and model revenue left on the table — then continue into setup.",
    source: "lead_magnet_audit",
  },
  {
    title: "ROI report generator",
    description: "Personalized 12-month recovery forecast tied to your vertical and ticket size.",
    source: "lead_magnet_roi",
  },
] as const;

export function LeadMagnetSection() {
  return (
    <section className="section" id="lead-magnets">
      <div className="wrap">
        <header className="section-lead section-lead--center">
          <p className="kicker kicker--dark">Free tools</p>
          <h2>See your numbers before you commit</h2>
          <p>Capture your ROI, then continue straight into self-serve setup — no sales call required.</p>
        </header>
        <div className="lead-magnet-grid">
          {MAGNETS.map(({ title, description, source }) => (
            <article key={source} className="lead-magnet-card">
              <h3>{title}</h3>
              <p>{description}</p>
              <Link href={onboardingHref({ source })} className="btn btn--copper">
                Get my free report
              </Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export default LeadMagnetSection;