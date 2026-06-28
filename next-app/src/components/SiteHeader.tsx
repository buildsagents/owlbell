"use client";

import { useEffect, useState } from "react";
import OwlLogo from "@/components/OwlLogo";

const NAV = [
  { id: "results", label: "Workflow" },
  { id: "how", label: "Agency" },
  { id: "honest-math", label: "ROI" },
  { id: "pricing", label: "Plans" },
];

export default function SiteHeader() {
  const [solid, setSolid] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setSolid(window.scrollY > 48);
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
    <header className={`site-header${solid ? " site-header--solid" : " site-header--hero"}`}>
      <nav className="site-nav wrap" aria-label="Main">
        <OwlLogo variant={solid ? "dark" : "light"} />

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
          <a href="mailto:hello@owlbell.xyz" className="site-nav-email">
            hello@owlbell.xyz
          </a>
          <button
            type="button"
            className="btn btn--copper btn--sm site-nav-cta"
            onClick={() => scrollTo("pricing")}
          >
            Start trial
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
          <a href="mailto:hello@owlbell.xyz" className="site-mobile-email">
            hello@owlbell.xyz
          </a>
          <button type="button" className="btn btn--copper btn--block" onClick={() => scrollTo("pricing")}>
            Start trial
          </button>
        </div>
      </div>
    </header>
  );
}