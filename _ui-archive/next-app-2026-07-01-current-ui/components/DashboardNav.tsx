'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV = [
  { href: '/dashboard',            label: 'Overview',      exact: true },
  { href: '/dashboard/calls',      label: 'Call History'              },
  { href: '/dashboard/settings',   label: 'Agent Settings'            },
  { href: '/dashboard/billing',    label: 'Billing'                   },
];

export default function DashboardNav() {
  const pathname = usePathname();

  return (
    <nav className="dash-nav">
      <div className="dash-nav-header">
        <Link href="/" className="dash-nav-logo">Owlbell</Link>
        <span className="dash-nav-subtitle">Dashboard</span>
      </div>

      <div className="dash-nav-links">
        {NAV.map(({ href, label, exact }) => {
          const active = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`dash-nav-link${active ? ' dash-nav-link--active' : ''}`}
            >
              {label}
            </Link>
          );
        })}
      </div>

      <div className="dash-nav-footer">
        <Link href="/" className="dash-nav-back">Back to site</Link>
      </div>
    </nav>
  );
}
