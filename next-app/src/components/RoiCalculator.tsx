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

  const breakevenDays = useMemo(() => {
    if (recoveredMonthly <= 0) return null;
    const daily = recoveredMonthly / 30;
    return Math.max(1, Math.ceil(1497 / daily));
  }, [recoveredMonthly]);

  return (
    <div className="roi-strip">
      <div className="wrap roi-strip-inner">
        <div className="roi-strip-copy">
          <h2>What voicemail is costing you</h2>
          <p>Drag the sliders — most plumbing shops underestimate missed calls.</p>
        </div>

        <div className="roi-strip-controls">
          <label className="roi-slider">
            <span className="roi-slider-top">
              <span>Calls missed per week</span>
              <strong className="num">{missedPerWeek}</strong>
            </span>
            <input
              type="range"
              min={0}
              max={40}
              value={missedPerWeek}
              onChange={(e) => setMissedPerWeek(Number(e.target.value))}
            />
          </label>

          <label className="roi-slider">
            <span className="roi-slider-top">
              <span>Average job value</span>
              <strong className="num">${avgJobValue.toLocaleString()}</strong>
            </span>
            <input
              type="range"
              min={150}
              max={1500}
              step={25}
              value={avgJobValue}
              onChange={(e) => setAvgJobValue(Number(e.target.value))}
            />
          </label>
        </div>

        <div className="roi-strip-result">
          <span className="roi-strip-label">Revenue at risk</span>
          <span className="roi-strip-value num">{formatCurrency(recoveredMonthly)}</span>
          <span className="roi-strip-hint">per month</span>
          {breakevenDays !== null && recoveredMonthly > 1497 && (
            <span className="roi-strip-breakeven">
              Launch plan pays for itself in ~{breakevenDays} days at this rate
            </span>
          )}
        </div>
      </div>
    </div>
  );
}