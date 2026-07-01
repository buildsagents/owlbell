import { PLUMBING_SCENARIOS } from "@/lib/plumbing-scenarios";

type Props = {
  limit?: number;
  className?: string;
};

export default function CallScenarioChips({ limit, className = "" }: Props) {
  const scenarios = limit ? PLUMBING_SCENARIOS.slice(0, limit) : PLUMBING_SCENARIOS;

  return (
    <ul className={`ops-scenarios${className ? ` ${className}` : ""}`} aria-label="Common plumbing call types">
      {scenarios.map((s) => (
        <li key={s.id} className={`ops-scenario ops-scenario--${s.urgency}`}>
          <span className="ops-scenario-label">{s.label}</span>
          <span className="ops-scenario-meta num">
            {s.afterHours ? "After hours" : "Business hrs"} - {s.avgValue}
          </span>
        </li>
      ))}
    </ul>
  );
}