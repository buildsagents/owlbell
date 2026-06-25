"use client";

import { useState } from "react";

const OWLBELL_MONTHLY = 297;

export default function MissedCallCalculator() {
  const [missedCalls, setMissedCalls] = useState(5);
  const [jobValue, setJobValue] = useState(400);

  const monthlyLoss = missedCalls * jobValue * 4.33;
  const jobsToPayForIt = Math.ceil(OWLBELL_MONTHLY / jobValue);
  const monthsOfOwlbell = Math.floor(monthlyLoss / OWLBELL_MONTHLY);

  return (
    <div className="calculator">
      <div className="calc-slider-row">
        <div className="calc-slider-header">
          <label>Calls missed per week</label>
          <span className="calc-slider-value">{missedCalls}</span>
        </div>
        <input
          type="range"
          min={0}
          max={20}
          step={1}
          value={missedCalls}
          onChange={(e) => setMissedCalls(Number(e.target.value))}
        />
      </div>

      <div className="calc-slider-row">
        <div className="calc-slider-header">
          <label>Average job ticket</label>
          <span className="calc-slider-value">${jobValue.toLocaleString()}</span>
        </div>
        <input
          type="range"
          min={100}
          max={2000}
          step={50}
          value={jobValue}
          onChange={(e) => setJobValue(Number(e.target.value))}
        />
      </div>

      <div className="calc-result">
        <div className="calc-result-label">You're losing every month</div>
        <div className="calc-result-num">
          ${Math.round(monthlyLoss).toLocaleString()}
        </div>
        <div className="calc-result-sub">
          That's <strong>${Math.round(monthlyLoss / 4.33).toLocaleString()}</strong> per missed call
        </div>

        {monthlyLoss > 0 && (
          <>
            <div className="calc-divider" />
            <div className="calc-result-label">What Owlbell costs</div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 6, margin: "4px 0 2px" }}>
              <span style={{ fontSize: 42, fontWeight: 800, letterSpacing: "-0.02em", color: "var(--good)", lineHeight: 1 }}>
                ${OWLBELL_MONTHLY}
              </span>
              <span style={{ color: "var(--muted)", fontSize: 15 }}>/mo</span>
            </div>
            <div className="calc-result-sub">
              <span className="calc-result-green">{jobsToPayForIt > 1 ? `${jobsToPayForIt} extra jobs` : "1 extra job"}</span> pays for it entirely.
              {monthsOfOwlbell > 1 && (
                <span style={{ display: "block", marginTop: 4 }}>
                  Owlbell could pay for itself <strong style={{ color: "var(--ink)" }}>{monthsOfOwlbell > 12 ? "every month" : `${monthsOfOwlbell}x over`}</strong> with what you're already losing.
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
