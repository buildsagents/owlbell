"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { computeRoi, buildOnboardingQueryFromRoi } from "@/lib/roi-math";
import { CTA_START_TRIAL, onboardingHref } from "@/lib/marketing-cta";
import type { VerticalSlug } from "@/lib/verticals";

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

type Props = {
  defaultVertical?: VerticalSlug;
};

export default function RoiCalculator({ defaultVertical }: Props) {
  const [missedPerWeek, setMissedPerWeek] = useState(12);
  const [avgJobValue, setAvgJobValue] = useState(400);

  const inputs = useMemo(
    () => ({ missedPerWeek, avgJobValue }),
    [missedPerWeek, avgJobValue],
  );

  const result = useMemo(() => computeRoi(inputs), [inputs]);

  const signupHref = useMemo(() => {
    const query = buildOnboardingQueryFromRoi(result, inputs);
    const extra = defaultVertical ? `&vertical=${defaultVertical}` : "";
    return `${onboardingHref()}?${query}${extra}`;
  }, [result, inputs, defaultVertical]);

  return (
    <div className="roi-strip" id="honest-math">
      <div className="wrap roi-strip-inner">
        <div className="roi-strip-copy">
          <h2>See your exact ROI</h2>
          <p>Drag the sliders — most service shops underestimate missed calls.</p>
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
          <span className="roi-strip-value num">{formatCurrency(result.recoveredMonthly)}</span>
          <span className="roi-strip-hint">per month</span>
          {result.breakevenDays !== null && (
            <span className="roi-strip-breakeven">
              Launch plan pays for itself in ~{result.breakevenDays} days at this rate
            </span>
          )}
          <Link href={signupHref} className="btn btn--copper roi-strip-cta">
            {CTA_START_TRIAL} with these numbers
          </Link>
        </div>
      </div>
    </div>
  );
}