import { cn } from "@/lib/utils";

const illustrations = {
  default: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="8" y="16" width="48" height="36" rx="4" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M8 24h48" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="16" cy="20" r="1.5" fill="currentColor" />
      <circle cx="21" cy="20" r="1.5" fill="currentColor" />
      <circle cx="26" cy="20" r="1.5" fill="currentColor" />
    </svg>
  ),
  calls: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="14" y="8" width="36" height="48" rx="6" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <rect x="20" y="14" width="24" height="2" rx="1" fill="currentColor" opacity="0.3" />
      <rect x="20" y="20" width="16" height="2" rx="1" fill="currentColor" opacity="0.3" />
      <rect x="26" y="34" width="12" height="12" rx="6" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M32 38v4M30 40h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="32" cy="44" r="1" fill="currentColor" />
      <path d="M20 28c0-2 2-3 4-3s4 1 4 3" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity="0.4" />
    </svg>
  ),
  messages: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="8" y="12" width="48" height="36" rx="6" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M32 48l-8-8h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <rect x="18" y="22" width="28" height="2" rx="1" fill="currentColor" opacity="0.25" />
      <rect x="18" y="28" width="20" height="2" rx="1" fill="currentColor" opacity="0.2" />
      <rect x="18" y="34" width="24" height="2" rx="1" fill="currentColor" opacity="0.15" />
    </svg>
  ),
  clients: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="24" cy="20" r="6" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M14 38c0-5.5 4.5-10 10-10s10 4.5 10 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="44" cy="26" r="4" stroke="currentColor" strokeWidth="1.5" fill="none" opacity="0.5" />
      <path d="M38 38c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.5" />
    </svg>
  ),
  analytics: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="10" y="8" width="44" height="48" rx="4" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M18 44V28" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M28 44V20" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M38 44V32" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M48 44V16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="48" cy="16" r="2" fill="currentColor" opacity="0.5" />
      <circle cx="28" cy="20" r="2" fill="currentColor" opacity="0.5" />
    </svg>
  ),
  leads: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 20h40M12 32h28M12 44h34" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.2" />
      <rect x="8" y="12" width="48" height="40" rx="6" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <circle cx="50" cy="22" r="7" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M50 19v6M47 22h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  search: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="26" cy="26" r="12" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <path d="M35 35l9 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <rect x="15" y="20" width="22" height="2" rx="1" fill="currentColor" opacity="0.15" />
    </svg>
  ),
  appointments: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="8" y="12" width="48" height="44" rx="4" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <rect x="8" y="22" width="48" height="2" fill="currentColor" opacity="0.15" />
      <rect x="12" y="28" width="12" height="8" rx="2" stroke="currentColor" strokeWidth="1" />
      <rect x="28" y="28" width="12" height="8" rx="2" stroke="currentColor" strokeWidth="1" opacity="0.5" />
      <rect x="44" y="28" width="8" height="8" rx="2" stroke="currentColor" strokeWidth="1" opacity="0.3" />
      <line x1="16" y1="10" x2="16" y2="16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="48" y1="10" x2="48" y2="16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  onboarding: (
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="10" y="8" width="44" height="48" rx="4" stroke="currentColor" strokeWidth="1.5" fill="none" />
      <circle cx="20" cy="22" r="3" stroke="currentColor" strokeWidth="1.5" />
      <path d="M17 28c0-1.7 1.3-3 3-3s3 1.3 3 3" stroke="currentColor" strokeWidth="1" strokeLinecap="round" />
      <circle cx="44" cy="22" r="3" stroke="currentColor" strokeWidth="1.5" opacity="0.5" />
      <rect x="14" y="36" width="36" height="2" rx="1" fill="currentColor" opacity="0.2" />
      <rect x="14" y="42" width="24" height="2" rx="1" fill="currentColor" opacity="0.15" />
      <rect x="34" y="42" width="16" height="2" rx="1" fill="currentColor" opacity="0.15" />
      <rect x="14" y="48" width="36" height="2" rx="1" fill="currentColor" opacity="0.1" />
    </svg>
  ),
};

export type IllustrationType = keyof typeof illustrations;

interface EmptyStateProps {
  title?: string;
  description?: string;
  illustration?: IllustrationType;
  icon?: React.ComponentType<{ className?: string }>;
  children?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  title = "No items found",
  description = "There are no items to display at this time.",
  illustration = "default",
  icon: _icon,
  children,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-16 text-center",
        className
      )}
    >
      <div className="mb-4 text-muted-foreground/40">
        {illustrations[illustration]}
      </div>
      <h3 className="text-lg font-semibold">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}
