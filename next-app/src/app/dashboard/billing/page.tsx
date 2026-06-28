'use client';

import { useEffect } from 'react';

const DASHBOARD_URL =
  (process.env.NEXT_PUBLIC_DASHBOARD_URL || 'https://app.owlbell.xyz').replace(/\/+$/, '');

export default function BillingRedirect() {
  useEffect(() => {
    window.location.replace(`${DASHBOARD_URL}/billing`);
  }, []);

  return (
    <main style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
      <p>Redirecting to billing…</p>
    </main>
  );
}