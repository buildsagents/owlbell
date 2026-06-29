"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CTA_START_TRIAL, onboardingHref } from "@/lib/marketing-cta";

const STORAGE_KEY = "owlbell_exit_intent_seen";

export function ExitIntentModal() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || sessionStorage.getItem(STORAGE_KEY)) return;

    const onLeave = (e: MouseEvent) => {
      if (e.clientY <= 0) {
        sessionStorage.setItem(STORAGE_KEY, "1");
        setOpen(true);
      }
    };

    document.addEventListener("mouseout", onLeave);
    return () => document.removeEventListener("mouseout", onLeave);
  }, []);

  if (!open) return null;

  return (
    <div className="pricing-modal-overlay" role="presentation" onClick={() => setOpen(false)}>
      <div
        className="pricing-modal exit-intent-modal"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <button type="button" className="pricing-modal-close" onClick={() => setOpen(false)} aria-label="Close">
          ✕
        </button>
        <h3>Before you go — free missed-call audit</h3>
        <p>
          See how many jobs you may be losing after hours. Start your free trial and get a personalized ROI report
          in onboarding.
        </p>
        <div className="exit-intent-actions">
          <Link href={onboardingHref({ source: "exit_intent" })} className="btn btn--copper btn--block">
            {CTA_START_TRIAL}
          </Link>
          <button type="button" className="btn btn--outline btn--block" onClick={() => setOpen(false)}>
            Maybe later
          </button>
        </div>
      </div>
    </div>
  );
}

export default ExitIntentModal;