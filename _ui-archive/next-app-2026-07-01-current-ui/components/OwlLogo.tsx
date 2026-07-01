import Link from "next/link";

type OwlLogoProps = {
  variant?: "light" | "dark";
  className?: string;
};

export default function OwlLogo({ variant = "dark", className = "" }: OwlLogoProps) {
  return (
    <Link href="/" className={`logo owl-logo owl-logo--${variant} ${className}`.trim()} aria-label="Owlbell home">
      <svg
        className="logo-mark owl-logo-mark"
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden
      >
        <rect x="2" y="2" width="36" height="36" rx="10" fill="currentColor" />
        <path d="M12 15.5c0-4.2 3.2-7.5 8-7.5s8 3.3 8 7.5v8.2c0 4.3-3.2 7.3-8 7.3s-8-3-8-7.3v-8.2z" fill="white" fillOpacity="0.96" />
        <path d="M10 14.2 6.9 10c3.1-.1 5.4.8 7 2.6L10 14.2zM30 14.2l3.1-4.2c-3.1-.1-5.4.8-7 2.6l3.9 1.6z" fill="white" fillOpacity="0.96" />
        <circle cx="16" cy="18" r="2.25" fill="currentColor" />
        <circle cx="24" cy="18" r="2.25" fill="currentColor" />
        <path d="M18 23h4l-2 2.2L18 23z" fill="currentColor" />
        <path d="M15.5 27.2c1.3 1 2.8 1.5 4.5 1.5s3.2-.5 4.5-1.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
      <span className="owl-logo-word">
        Owl<span>bell</span>
      </span>
    </Link>
  );
}
