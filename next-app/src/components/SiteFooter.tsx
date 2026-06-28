export default function SiteFooter() {
  return (
    <footer className="site-footer site-footer--dispatch">
      <div className="wrap site-footer-inner">
        <div className="site-footer-brand">
          <div className="footer-logo">
            Owl<span>bell</span>
          </div>
          <p>Managed reception for US plumbing contractors. Humans set it up. Every call answered.</p>
        </div>

        <div className="site-footer-contact">
          <a href="tel:+18885550199" className="num">(888) 555-0199</a>
          <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a>
        </div>

        <nav className="site-footer-nav" aria-label="Footer">
          <a href="#how">Agency</a>
          <a href="#pricing">Plans</a>
          <a href="/privacy">Privacy</a>
          <a href="/terms">Terms</a>
        </nav>
      </div>

      <div className="wrap site-footer-bottom">
        <p>© {new Date().getFullYear()} Owlbell · Plumbing only</p>
      </div>
    </footer>
  );
}