import { Link, useLocation } from "react-router-dom";
import { useUIStore } from "@/stores/ui-store";
import { useAuthStore } from "@/stores/auth-store";
import { useCallStore } from "@/stores/call-store";
import { cn } from "@/lib/utils";
import {
  MAIN_NAVIGATION,
  SETTINGS_NAVIGATION,
  ADMIN_NAVIGATION,
  AGENCY_NAVIGATION,
  OUTREACH_NAVIGATION,
} from "@/lib/constants";
import { hasPermission } from "@/lib/permissions";
import {
  LayoutDashboard,
  Phone,
  BarChart3,
  MessageSquare,
  CalendarDays,
  Bot,
  Clock,
  BookOpen,
  Plug,
  Bell,
  Users,
  CreditCard,
  ChevronLeft,
  ChevronRight,
  PhoneCall,
  UserPlus,
  Layers,
  Send,
} from "lucide-react";
import type { NavItem } from "@/lib/constants";

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  "layout-dashboard": LayoutDashboard,
  phone: Phone,
  "bar-chart-3": BarChart3,
  "message-square": MessageSquare,
  "calendar-days": CalendarDays,
  bot: Bot,
  clock: Clock,
  "book-open": BookOpen,
  plug: Plug,
  bell: Bell,
  users: Users,
  "credit-card": CreditCard,
  "user-plus": UserPlus,
  layers: Layers,
  send: Send,
};

function NavIcon({ icon }: { icon: string }) {
  const Icon = iconMap[icon] || LayoutDashboard;
  return <Icon className="h-5 w-5" />;
}

function SidebarNavItem({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const location = useLocation();
  const isActive = location.pathname.startsWith(item.path);
  const activeCalls = useCallStore((s) => s.activeCalls.length);
  const user = useAuthStore((s) => s.user);

  if (item.requiredPermission && user) {
    if (!hasPermission(user.role, item.requiredPermission.split(":")[0], item.requiredPermission.split(":")[1])) {
      return null;
    }
  }

  return (
    <Link
      to={item.path}
      className={cn(
        "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
        isActive
          ? "bg-primary/10 text-primary"
          : "text-muted-foreground hover:bg-accent hover:text-foreground"
      )}
    >
      <NavIcon icon={item.icon} />
      {!collapsed && (
        <>
          <span className="flex-1">{item.label}</span>
          {item.badge === "active_calls" && activeCalls > 0 && (
            <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-emerald-500 px-1.5 text-[10px] font-bold text-white">
              {activeCalls}
            </span>
          )}
        </>
      )}
    </Link>
  );
}

export function Sidebar() {
  const { sidebarCollapsed, setSidebarCollapsed } = useUIStore();
  const tenant = useAuthStore((s) => s.tenant);

  return (
    <aside
      className={cn(
        "fixed left-0 top-0 z-40 flex h-screen flex-col border-r bg-sidebar-background transition-all duration-300",
        sidebarCollapsed ? "w-16" : "w-64"
      )}
    >
      <div className="flex h-16 items-center gap-2 border-b px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <PhoneCall className="h-4 w-4" />
        </div>
        {!sidebarCollapsed && (
          <span className="text-lg font-bold tracking-tight">Owlbell</span>
        )}
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        <div className="mb-4 space-y-1">
          {MAIN_NAVIGATION.map((item) => (
            <SidebarNavItem key={item.path} item={item} collapsed={sidebarCollapsed} />
          ))}
        </div>

        {!sidebarCollapsed && (
          <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Settings
          </p>
        )}
        <div className="mb-4 space-y-1">
          {SETTINGS_NAVIGATION.map((item) => (
            <SidebarNavItem key={item.path} item={item} collapsed={sidebarCollapsed} />
          ))}
        </div>

        {!sidebarCollapsed && (
          <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Admin
          </p>
        )}
        <div className="space-y-1">
          {ADMIN_NAVIGATION.map((item) => (
            <SidebarNavItem key={item.path} item={item} collapsed={sidebarCollapsed} />
          ))}
        </div>

        {!sidebarCollapsed && (
          <p className="mb-2 mt-4 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Agency
          </p>
        )}
        <div className="space-y-1">
          {AGENCY_NAVIGATION.map((item) => (
            <SidebarNavItem key={item.path} item={item} collapsed={sidebarCollapsed} />
          ))}
        </div>

        {!sidebarCollapsed && (
          <p className="mb-2 mt-4 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Growth
          </p>
        )}
        <div className="space-y-1">
          {OUTREACH_NAVIGATION.map((item) => (
            <SidebarNavItem key={item.path} item={item} collapsed={sidebarCollapsed} />
          ))}
        </div>
      </nav>

      <div className="border-t p-3">
        {tenant && !sidebarCollapsed && (
          <div className="mb-2 flex items-center gap-2 px-2">
            <div className="h-2 w-2 rounded-full bg-emerald-500" />
            <span className="text-xs text-muted-foreground truncate">{tenant.businessName}</span>
          </div>
        )}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="flex w-full items-center justify-center rounded-lg p-2 text-muted-foreground hover:bg-accent transition-colors"
          aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {sidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>
    </aside>
  );
}
