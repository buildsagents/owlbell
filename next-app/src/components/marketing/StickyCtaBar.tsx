"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CTA_LAUNCH_AI, onboardingHref } from "@/lib/marketing-cta";

export function StickyCtaBar() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 480);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  if (!visible) return null;

  return (
    <div className="sticky-cta-bar" role="region" aria-label="Get started">
      <div className="sticky-cta-bar-inner wrap">
        <p>Launch in under 15 min — fully self-serve</p>
        <Link href={onboardingHref()} className="btn btn--copper btn--sm">
          {CTA_LAUNCH_AI}
        </Link>
      </div>
    </div>
  );
}

export default StickyCtaBar;