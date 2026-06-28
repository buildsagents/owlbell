import Link from "next/link";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";

type LegalDocumentProps = {
  title: string;
  effectiveDate: string;
  children: React.ReactNode;
};

export default function LegalDocument({ title, effectiveDate, children }: LegalDocumentProps) {
  return (
    <div className="site">
      <SiteHeader />
      <main className="site-main legal-page">
        <article className="wrap legal-article">
          <header className="legal-header">
            <Link href="/" className="legal-back">
              ← Back to owlbell.xyz
            </Link>
            <h1>{title}</h1>
            <p className="legal-meta">Effective date: {effectiveDate}</p>
          </header>
          <div className="legal-body">{children}</div>
        </article>
      </main>
      <SiteFooter />
    </div>
  );
}