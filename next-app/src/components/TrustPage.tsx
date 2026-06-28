import Link from "next/link";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";

type TrustPageProps = {
  title: string;
  meta?: string;
  children: React.ReactNode;
  wide?: boolean;
};

export default function TrustPage({ title, meta, children, wide }: TrustPageProps) {
  return (
    <div className="site">
      <SiteHeader />
      <main className="site-main legal-page">
        <article className={`wrap legal-article${wide ? " legal-article--wide" : ""}`}>
          <header className="legal-header">
            <Link href="/" className="legal-back">
              ← Back to owlbell.xyz
            </Link>
            <h1>{title}</h1>
            {meta ? <p className="legal-meta">{meta}</p> : null}
          </header>
          <div className="legal-body">{children}</div>
        </article>
      </main>
      <SiteFooter />
    </div>
  );
}