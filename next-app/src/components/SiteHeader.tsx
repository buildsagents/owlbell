"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import OwlLogo from "@/components/OwlLogo";
import { CTA_START_TRIAL, onboardingHref } from "@/lib/marketing-cta";

const SCROLL_NAV = [
  { id: "results", label: "Workflow" },
  { id: "how", label: "How it works" },
  { id: "honest-math", label: "ROI" },
  { id: "pricing", label: "Plans" },
];

const PAGE_NAV = [
  { href: "/how-it-works", label: "How it works" },
  { href: "/compare", label: "Compare" },
  { href: "/demo", label: "Demo" },
  { href: "/faq", label: "FAQ" },
];

export default function SiteHeader() {
  const pathname = usePathname();
  const onHome = pathname === "/";
  const [solid, setSolid] = useState(!onHome);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    if (!onHome) {
      setSolid(true);
      return;
    }

    const onScroll = () => setSolid(window.scrollY > 48);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [onHome]);

  useEffect(() => {
    document.body.style.overflow = menuOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [menuOpen]);

  const scrollTo = (id: string) => {
    setMenuOpen(false);
    if (!onHome) {
      window.location.href = `/#${id}`;
      return;
    }
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const closeMenu = () => setMenuOpen(false);

  return (
    <header className={`site-header${solid ? " site-header--solid" : " site-header--hero"}`}>
      <nav className="site-nav wrap" aria-label="Main">
        <OwlLogo variant={solid ? "dark" : "light"} />

        <div className="site-nav-links">
          {SCROLL_NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              className="site-nav-link"
              onClick={() => scrollTo(item.id)}
            >
              {item.label}
            </button>
          ))}
          {PAGE_NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`site-nav-link site-nav-link--page${pathname === item.href ? " site-nav-link--active" : ""}`}
            >
              {item.label}
            </Link>
          ))}
        </div>

        <div className="site-nav-actions">
          <a href="mailto:hello@owlbell.xyz" className="site-nav-email">
            hello@owlbell.xyz
          </a>
          <Link href={onboardingHref({ source: "header" })} className="btn btn--copper btn--sm site-nav-cta">
            {CTA_START_TRIAL}
          </Link>
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
          {SCROLL_NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              className="site-mobile-link"
              onClick={() => scrollTo(item.id)}
            >
              {item.label}
            </button>
          ))}
          {PAGE_NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="site-mobile-link site-mobile-link--page"
              onClick={closeMenu}
            >
              {item.label}
            </Link>
          ))}
          <a href="mailto:hello@owlbell.xyz" className="site-mobile-email">
            hello@owlbell.xyz
          </a>
          <Link href={onboardingHref({ source: "header_mobile" })} className="btn btn--copper btn--block" onClick={closeMenu}>
            {CTA_START_TRIAL}
          </Link>
        </div>
      </div>
    </header>
  );
}