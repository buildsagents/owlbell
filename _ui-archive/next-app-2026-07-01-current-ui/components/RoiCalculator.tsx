"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { computeRoi } from "@/lib/roi-math";

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    maximumFractionDigits: 0,
  }).format(value);
}

function AnimatedNumber({ value, duration = 400 }: { value: number; duration?: number }) {
  const [display, setDisplay] = useState(value);
  const prevRef = useRef(value);
  const rafRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    const from = prevRef.current;
    const diff = value - from;
    if (diff === 0) return;
    prevRef.current = value;
    const start = performance.now();

    function tick(now: number) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - (1 - progress) * (1 - progress);
      setDisplay(Math.round(from + diff * eased));
      if (progress < 1) rafRef.current = requestAnimationFrame(tick);
    }

    rafRef.current = requestAnimationFrame(tick);
    return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
  }, [value, duration]);

  return <>{formatCurrency(display)}</>;
}

export default function RoiCalculator() {
  const [missedPerWeek, setMissedPerWeek] = useState(12);
  const [avgJobValue, setAvgJobValue] = useState(400);

  const inputs = useMemo(() => ({ missedPerWeek, avgJobValue }), [missedPerWeek, avgJobValue]);
  const result = useMemo(() => computeRoi(inputs), [inputs]);

  return (
    <section className="roi-section section" id="roi">
      <div className="wrap roi-grid">
        <div className="roi-copy">
          <span className="section-label">ROI calculator</span>
          <h2>How much are missed calls costing you?</h2>
          <p>Most plumbing shops underestimate after-hours call volume. Slide to see your number.</p>
        </div>

        <div className="roi-slider-group">
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
              <strong className="num">&pound;{avgJobValue.toLocaleString()}</strong>
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

        <div className="roi-result">
          <span className="roi-result-label">Monthly revenue at risk</span>
          <span className="roi-result-value num">
            <AnimatedNumber value={result.recoveredMonthly} />
          </span>
          <span className="roi-result-hint">per month in missed calls</span>
          {result.breakevenDays !== null && (
            <span className="roi-breakeven">
              Pays for itself in ~{result.breakevenDays} days
            </span>
          )}
          <div className="roi-cta">
            <Link href="/onboarding?source=roi" className="btn btn--primary btn--sm">
              Book a Demo
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
