import Link from "next/link";
import { onboardingHref } from "@/lib/marketing-cta";

const STEPS = [
  {
    id: "configure",
    label: "You configure",
    detail:
      "Pick your vertical, voice, scripts, calendar, and emergency rules in onboarding — saved to the cloud, resumable on any device.",
  },
  {
    id: "answer",
    label: "AI answers",
    detail:
      "Callers reach your Owlbell inbound line. The AI picks up in under two seconds — nights, weekends, and lunch rush included.",
  },
  {
    id: "notify",
    label: "You get the text",
    detail:
      "A plain-English summary hits your phone: caller name, issue, time slot, and estimated job value. Review on your schedule.",
  },
];

export default function HowItWorksSection() {
  return (
    <section className="section section--warm" id="how">
      <div className="wrap">
        <header className="section-lead">
          <p className="kicker kicker--dark">How it works</p>
          <h2>Three things happen on every call</h2>
          <p>Self-serve setup. Retell-powered voice. First test call in minutes.</p>
        </header>

        <ol className="flow-steps">
          {STEPS.map((step, index) => (
            <li key={step.id} className="flow-step">
              <span className="flow-step-num num">{String(index + 1).padStart(2, "0")}</span>
              <div>
                <h3>{step.label}</h3>
                <p>{step.detail}</p>
              </div>
            </li>
          ))}
        </ol>

        <p className="vertical-selector-cta">
          <Link href={onboardingHref({ source: "how_section" })} className="btn btn--copper">
            Start free trial
          </Link>
        </p>
      </div>
    </section>
  );
}