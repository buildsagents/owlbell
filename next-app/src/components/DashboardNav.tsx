'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV = [
  { href: '/dashboard',            label: '📊 Overview',       exact: true },
  { href: '/dashboard/calls',      label: '📞 Call History'              },
  { href: '/dashboard/settings',   label: '🤖 Agent Settings'            },
  { href: '/dashboard/billing',    label: '💳 Billing'                   },
];

export default function DashboardNav() {
  const pathname = usePathname();

  return (
    <nav style={{
      width: '220px',
      flexShrink: 0,
      borderRight: '1px solid var(--line)',
      padding: '24px 0',
      display: 'flex',
      flexDirection: 'column',
      gap: '4px',
      backgroundColor: 'var(--panel)',
    }}>
      <div style={{
        padding: '0 20px 20px',
        borderBottom: '1px solid var(--line)',
        marginBottom: '8px',
      }}>
        <div className="logo">Owl<span>bell</span></div>
        <div style={{ fontSize: '12px', color: 'var(--muted)', marginTop: '4px' }}>Dashboard</div>
      </div>

      {NAV.map(({ href, label, exact }) => {
        const active = exact ? pathname === href : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            style={{
              display: 'block',
              padding: '10px 20px',
              borderRadius: '8px',
              margin: '0 8px',
              fontSize: '14px',
              fontWeight: active ? 700 : 500,
              color: active ? 'var(--brand2)' : 'var(--muted)',
              backgroundColor: active ? 'rgba(245,158,11,0.08)' : 'transparent',
              textDecoration: 'none',
              transition: 'background 0.15s, color 0.15s',
            }}
          >
            {label}
          </Link>
        );
      })}

      <div style={{ flex: 1 }} />

      <div style={{ padding: '0 8px' }}>
        <Link
          href="/"
          style={{
            display: 'block',
            padding: '10px 20px',
            borderRadius: '8px',
            fontSize: '14px',
            color: 'var(--muted)',
            textDecoration: 'none',
          }}
        >
          ← Back to site
        </Link>
      </div>
    </nav>
  );
}
