"use client";

import { useMemo, useState } from "react";

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

export default function RoiCalculator() {
  const [missedPerWeek, setMissedPerWeek] = useState(12);
  const [avgJobValue, setAvgJobValue] = useState(400);

  const recoveredMonthly = useMemo(
    () => Math.max(0, missedPerWeek * 4 * avgJobValue),
    [missedPerWeek, avgJobValue]
  );

  return (
    <div className="roi-card agency-card">
      <h2 className="roi-card-title">What Voicemail Is Costing You</h2>

      <div className="roi-field">
        <label htmlFor="missed-calls">Calls missed per week</label>
        <input
          id="missed-calls"
          type="number"
          min={0}
          max={200}
          value={missedPerWeek}
          onChange={(e) => setMissedPerWeek(Math.max(0, Number(e.target.value) || 0))}
        />
      </div>

      <div className="roi-field">
        <label htmlFor="avg-job">Average job value</label>
        <div className="roi-input-prefix">
          <span className="roi-prefix">$</span>
          <input
            id="avg-job"
            type="number"
            min={0}
            max={10000}
            step={50}
            value={avgJobValue}
            onChange={(e) => setAvgJobValue(Math.max(0, Number(e.target.value) || 0))}
          />
        </div>
      </div>

      <div className="roi-result">
        <span className="roi-result-label">Potential recovered</span>
        <span className="roi-result-value">{formatCurrency(recoveredMonthly)}/mo</span>
        <span className="roi-result-hint">monthly revenue at risk</span>
      </div>
    </div>
  );
}