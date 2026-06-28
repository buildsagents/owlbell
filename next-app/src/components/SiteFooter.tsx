const FOOTER_LINKS = [
  { id: "results", label: "Results" },
  { id: "how", label: "How it works" },
  { id: "dashboard", label: "Dashboard" },
  { id: "honest-math", label: "ROI" },
  { id: "pricing", label: "Pricing" },
];

export default function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="wrap site-footer-inner">
        <div className="site-footer-brand">
          <div className="owl-logo-text site-footer-logo">
            Owl<span>bell</span>
          </div>
          <p>Your AI receptionist agency — built exclusively for plumbing companies.</p>
        </div>

        <nav className="site-footer-nav" aria-label="Footer">
          {FOOTER_LINKS.map((link) => (
            <a key={link.id} href={`#${link.id}`}>
              {link.label}
            </a>
          ))}
        </nav>

        <div className="site-footer-contact">
          <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a>
          <span>White-glove onboarding · subscribe online</span>
        </div>
      </div>

      <div className="wrap site-footer-bottom">
        <p>© {new Date().getFullYear()} Owlbell. All rights reserved.</p>
        <nav className="site-footer-legal" aria-label="Legal">
          <a href="/privacy">Privacy Policy</a>
          <a href="/terms">Terms of Service</a>
        </nav>
      </div>
    </footer>
  );
}
