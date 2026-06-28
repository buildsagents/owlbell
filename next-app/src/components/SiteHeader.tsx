"use client";

import { useEffect, useState } from "react";
import OwlLogo from "@/components/OwlLogo";

const NAV = [
  { id: "results", label: "Results" },
  { id: "how", label: "How it works" },
  { id: "dashboard", label: "Dashboard" },
  { id: "honest-math", label: "ROI" },
  { id: "pricing", label: "Pricing" },
];

export default function SiteHeader() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <header className={`site-header${scrolled ? " site-header--scrolled" : ""}`}>
      <nav className="site-nav wrap">
        <OwlLogo />

        <div className="site-nav-links">
          {NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              className="site-nav-link"
              onClick={() => scrollTo(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <button
          type="button"
          className="agency-btn agency-btn--primary agency-btn--sm site-nav-cta"
          onClick={() => scrollTo("pricing")}
        >
          Get Started
        </button>
      </nav>
    </header>
  );
}
