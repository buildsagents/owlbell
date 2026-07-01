import { AnimatePresence } from "framer-motion";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { PageTransition } from "@/components/shared/page-transition";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/ui-store";
import { useLocation } from "react-router-dom";

export function AppLayout({ children }: { children: React.ReactNode }) {
  const sidebarCollapsed = useUIStore((s) => s.sidebarCollapsed);
  const location = useLocation();

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <div
        className={cn(
          "transition-[margin] duration-300 ease-out",
          "lg:ml-64",
          sidebarCollapsed && "lg:ml-16"
        )}
      >
        <Header />
        <main className="pt-16">
          <div className="p-4 sm:p-6">
            <AnimatePresence mode="wait">
              <PageTransition key={location.pathname}>
                {children}
              </PageTransition>
            </AnimatePresence>
          </div>
        </main>
      </div>
    </div>
  );
}
