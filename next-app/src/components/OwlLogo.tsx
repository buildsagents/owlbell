import Link from "next/link";

export default function OwlLogo() {
  return (
    <Link href="/" className="owl-logo" aria-label="Owlbell home">
      <svg
        className="owl-logo-icon"
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden
      >
        <circle cx="16" cy="16" r="15" fill="#f59e0b" />
        <ellipse cx="11" cy="14" rx="4.5" ry="5" fill="#fff" />
        <ellipse cx="21" cy="14" rx="4.5" ry="5" fill="#fff" />
        <circle cx="11" cy="14" r="2.2" fill="#0f172a" />
        <circle cx="21" cy="14" r="2.2" fill="#0f172a" />
        <path
          d="M16 19.5c-2.2 0-4 1.2-4.8 3 1.6 1.2 3.2 1.8 4.8 1.8s3.2-.6 4.8-1.8c-.8-1.8-2.6-3-4.8-3z"
          fill="#fff"
        />
        <path d="M10 8.5c1.5-2 3.5-3 6-3s4.5 1 6 3" stroke="#d97706" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <span className="owl-logo-text">
        Owl<span>bell</span>
      </span>
    </Link>
  );
}