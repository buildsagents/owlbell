import DashboardNav from '@/components/DashboardNav';

export const metadata = {
  title: 'Dashboard - Owlbell',
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="dash-layout">
      <DashboardNav />
      <div className="dash-main">
        <header className="dash-topbar">
          <span className="dash-topbar-support">
            Need help? <a href="mailto:hello@owlbell.xyz">Email support</a>
          </span>
        </header>
        <main className="dash-content">
          {children}
        </main>
      </div>
    </div>
  );
}
