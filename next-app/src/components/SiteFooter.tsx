export default function SiteFooter() {
  return (
    <footer className="site-footer site-footer--dispatch">
      <div className="wrap site-footer-inner">
        <div className="site-footer-brand">
          <div className="footer-logo">
            Owl<span>bell</span>
          </div>
          <p>AI receptionist for US service businesses. Self-serve setup. Every call answered.</p>
        </div>

        <div className="site-footer-contact">
          <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a>
        </div>

        <nav className="site-footer-nav" aria-label="Footer">
          <a href="/about">About</a>
          <a href="/faq">FAQ</a>
          <a href="/demo">Sample call</a>
          <a href="/how-it-works">How it works</a>
          <a href="/#pricing">Plans</a>
          <a href="/privacy">Privacy</a>
          <a href="/terms">Terms</a>
        </nav>
      </div>

      <div className="wrap site-footer-bottom">
        <p>© {new Date().getFullYear()} Owlbell · Plumbing, HVAC, dental &amp; more</p>
        <p className="site-footer-entity">Owlbell · Managed reception services</p>
      </div>
    </footer>
  );
}