import Link from "next/link";
import OwlLogo from "@/components/OwlLogo";

export default function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="wrap footer-grid">
        <div className="footer-brand">
          <OwlLogo />
          <p>
            Managed phone reception for plumbing companies. We set up the voice, scripts, routing,
            and call reviews so missed calls turn into booked jobs.
          </p>
        </div>

        <div className="footer-col">
          <h4>Product</h4>
          <Link href="/#how-it-works">How it works</Link>
          <Link href="/#features">Features</Link>
          <Link href="/#pricing">Pricing</Link>
          <Link href="/demo">Live demo</Link>
          <Link href="/compare">Compare</Link>
        </div>

        <div className="footer-col">
          <h4>Resources</h4>
          <Link href="/faq">FAQ</Link>
          <Link href="/about">About</Link>
          <Link href="/plumbing-ai-receptionist">Services</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/terms">Terms</Link>
        </div>

        <div className="footer-col">
          <h4>Contact</h4>
          <a href="mailto:hello@owlbell.xyz">hello@owlbell.xyz</a>
          <p style={{ fontSize: "0.8125rem", color: "var(--gray-400)", marginTop: "8px" }}>
            Replies weekdays. Setup starts from the onboarding form.
          </p>
        </div>
      </div>

      <div className="wrap footer-bottom">
        <p>&copy; {new Date().getFullYear()} Owlbell. Plumbing contractors.</p>
        <p>Managed reception &amp; voice operations</p>
      </div>
    </footer>
  );
}
