"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import OwlLogo from "@/components/OwlLogo";

const NAV_ITEMS = [
  { id: "how-it-works", label: "How it works" },
  { id: "features", label: "Features" },
  { id: "pricing", label: "Pricing" },
  { href: "/demo", label: "Demo" },
  { href: "/faq", label: "FAQ" },
];

export default function SiteHeader() {
  const pathname = usePathname();
  const onHome = pathname === "/";
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = menuOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [menuOpen]);

  const scrollTo = (id: string) => {
    setMenuOpen(false);
    if (!onHome) { window.location.assign(`/#${id}`); return; }
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <header className={`site-header${scrolled ? " site-header--bordered" : ""}`}>
      <nav className="wrap site-nav" aria-label="Main">
        <OwlLogo />

        <div className="site-nav-links">
          {NAV_ITEMS.map((item) =>
            "id" in item ? (
              <button key={item.id} type="button" className="site-nav-link" onClick={() => scrollTo(item.id!)}>
                {item.label}
              </button>
            ) : (
              <Link key={item.href} href={item.href} className="site-nav-link">
                {item.label}
              </Link>
            )
          )}
        </div>

        <div className="site-nav-actions">
          <Link href="mailto:hello@owlbell.xyz" className="site-nav-link" style={{ fontSize: "0.8125rem" }}>
            hello@owlbell.xyz
          </Link>
          <Link href="/onboarding?source=header" className="btn btn--primary btn--sm">
            Book a Demo
          </Link>
          <button
            type="button"
            className="site-nav-toggle"
            aria-expanded={menuOpen}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            onClick={() => setMenuOpen((o) => !o)}
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden>
              <rect y="3" width="18" height="2" rx="1" fill="currentColor" />
              <rect y="8" width="18" height="2" rx="1" fill="currentColor" />
              <rect y="13" width="18" height="2" rx="1" fill="currentColor" />
            </svg>
          </button>
        </div>
      </nav>

      <div
        className="site-mobile-menu"
        style={{
          display: menuOpen ? "block" : "none",
          animation: menuOpen ? "fade-in 0.2s ease-out" : "none",
        }}
      >
        <div
          className="site-mobile-menu-inner"
          style={{
            animation: menuOpen ? "slide-up 0.25s cubic-bezier(0.16, 1, 0.3, 1)" : "none",
          }}
        >
          {NAV_ITEMS.map((item) =>
            "id" in item ? (
              <button key={item.id} type="button" className="site-mobile-link" onClick={() => scrollTo(item.id!)}>
                {item.label}
              </button>
            ) : (
              <Link key={item.href} href={item.href} className="site-mobile-link" onClick={() => setMenuOpen(false)}>
                {item.label}
              </Link>
            )
          )}
          <Link
            href="/onboarding?source=header_mobile"
            className="btn btn--primary btn--block"
            style={{ marginTop: "8px" }}
            onClick={() => setMenuOpen(false)}
          >
            Book a Demo
          </Link>
        </div>
      </div>
    </header>
  );
}
