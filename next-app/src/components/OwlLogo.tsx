import Link from "next/link";

type OwlLogoProps = {
  variant?: "light" | "dark";
};

export default function OwlLogo({ variant = "dark" }: OwlLogoProps) {
  return (
    <Link href="/" className={`owl-logo owl-logo--${variant}`} aria-label="Owlbell home">
      <svg
        className="owl-logo-mark"
        viewBox="0 0 32 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden
      >
        <rect width="32" height="32" rx="8" fill="currentColor" fillOpacity="0.12" />
        <circle cx="12" cy="15" r="3" fill="currentColor" />
        <circle cx="20" cy="15" r="3" fill="currentColor" />
        <path
          d="M16 20c-2 0-3.5 1-4 2.5 1.2.8 2.5 1.2 4 1.2s2.8-.4 4-1.2c-.5-1.5-2-2.5-4-2.5z"
          fill="currentColor"
          fillOpacity="0.85"
        />
      </svg>
      <span className="owl-logo-word">
        Owl<span>bell</span>
      </span>
    </Link>
  );
}