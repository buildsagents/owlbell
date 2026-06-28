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
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = menuOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [menuOpen]);

  const scrollTo = (id: string) => {
    setMenuOpen(false);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <header className={`site-header${scrolled ? " site-header--scrolled" : ""}`}>
      <nav className="site-nav wrap" aria-label="Main">
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

        <div className="site-nav-actions">
          <button
            type="button"
            className="agency-btn agency-btn--primary agency-btn--sm site-nav-cta"
            onClick={() => scrollTo("pricing")}
          >
            Get Started
          </button>

          <button
            type="button"
            className="site-nav-toggle"
            aria-expanded={menuOpen}
            aria-controls="site-mobile-menu"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <span className="site-nav-toggle-bar" />
            <span className="site-nav-toggle-bar" />
            <span className="site-nav-toggle-bar" />
          </button>
        </div>
      </nav>

      <div
        id="site-mobile-menu"
        className={`site-mobile-menu${menuOpen ? " site-mobile-menu--open" : ""}`}
        hidden={!menuOpen}
      >
        <div className="site-mobile-menu-inner">
          {NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              className="site-mobile-link"
              onClick={() => scrollTo(item.id)}
            >
              {item.label}
            </button>
          ))}
          <button
            type="button"
            className="agency-btn agency-btn--primary agency-btn--block"
            onClick={() => scrollTo("pricing")}
          >
            Get Started
          </button>
        </div>
      </div>
    </header>
  );
}