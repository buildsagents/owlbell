import DashboardNav from '@/components/DashboardNav';

export const metadata = {
  title: 'Dashboard — Owlbell',
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: 'flex',
      minHeight: '100vh',
      backgroundColor: 'var(--bg)',
    }}>
      <DashboardNav />

      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
      }}>
        {/* Top bar */}
        <div style={{
          height: '60px',
          borderBottom: '1px solid var(--line)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          padding: '0 28px',
          gap: '16px',
          backgroundColor: 'var(--panel)',
          flexShrink: 0,
        }}>
          <span style={{ fontSize: '13px', color: 'var(--muted)' }}>
            Need help? Email <a href="mailto:hello@owlbell.xyz" style={{ color: 'var(--accent)' }}>support</a>
          </span>
        </div>

        {/* Page content */}
        <main style={{ flex: 1, padding: '28px', overflowY: 'auto' }}>
          {children}
        </main>
      </div>
    </div>
  );
}
