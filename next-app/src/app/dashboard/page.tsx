'use client';

import { useEffect } from 'react';

const DASHBOARD_URL =
  (process.env.NEXT_PUBLIC_DASHBOARD_URL || 'https://app.owlbell.xyz').replace(/\/+$/, '');

export default function DashboardRedirect() {
  useEffect(() => {
    window.location.replace(`${DASHBOARD_URL}/dashboard`);
  }, []);

  return (
    <main style={{ padding: '2rem', fontFamily: 'system-ui, sans-serif' }}>
      <p>Redirecting to the Owlbell dashboard…</p>
    </main>
  );
}