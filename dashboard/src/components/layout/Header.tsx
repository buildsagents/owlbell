import { useUIStore } from "@/stores/ui-store";
import { useAuthStore } from "@/stores/auth-store";
import { useWebSocketStore } from "@/stores/websocket-store";
import { useNotificationStore } from "@/stores/notification-store";
import { cn } from "@/lib/utils";
import { useTheme } from "@/hooks/use-theme";
import {
  Bell,
  Moon,
  Sun,
  Monitor,
  Search,
  Menu,
  LogOut,
  User,
  Settings,
} from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";

export function Header() {
  const { sidebarCollapsed, setSidebarOpen } = useUIStore();
  const { user, logout } = useAuthStore();
  const wsStatus = useWebSocketStore((s) => s.status);
  const { unreadCount, setPanelOpen } = useNotificationStore();
  const { theme, setTheme } = useTheme();
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header
      className={cn(
        "fixed right-0 top-0 z-30 flex h-16 items-center justify-between border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60 transition-all duration-300",
        "left-0 lg:left-64",
        sidebarCollapsed && "lg:left-16"
      )}
    >
      <div className="flex items-center gap-3">
        <button
          onClick={() => setSidebarOpen(true)}
          className="rounded-lg p-2 text-muted-foreground hover:bg-accent lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div className="relative hidden sm:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search calls, messages..."
            className="h-9 w-64 rounded-lg border bg-transparent py-2 pl-9 pr-4 text-sm outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* WebSocket Status */}
        <div
          className={cn(
            "hidden h-2 w-2 rounded-full md:block",
            wsStatus === "connected" && "bg-emerald-500",
            wsStatus === "connecting" && "bg-amber-500 animate-pulse",
            wsStatus === "reconnecting" && "bg-amber-500 animate-pulse",
            (wsStatus === "disconnected" || wsStatus === "error") && "bg-rose-500"
          )}
          title={`WebSocket: ${wsStatus}`}
        />

        {/* Theme Toggle */}
        <div className="flex items-center rounded-lg border">
          <button
            onClick={() => setTheme("light")}
            className={cn(
              "rounded-l-lg p-1.5 transition-colors",
              theme === "light" ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Sun className="h-4 w-4" />
          </button>
          <button
            onClick={() => setTheme("system")}
            className={cn(
              "p-1.5 transition-colors",
              theme === "system" ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Monitor className="h-4 w-4" />
          </button>
          <button
            onClick={() => setTheme("dark")}
            className={cn(
              "rounded-r-lg p-1.5 transition-colors",
              theme === "dark" ? "bg-accent text-foreground" : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Moon className="h-4 w-4" />
          </button>
        </div>

        {/* Notifications */}
        <button
          onClick={() => setPanelOpen(true)}
          className="relative rounded-lg p-2 text-muted-foreground hover:bg-accent"
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white">
              {unreadCount}
            </span>
          )}
        </button>

        {/* Profile */}
        <div className="relative" ref={profileRef}>
          <button
            onClick={() => setProfileOpen(!profileOpen)}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary"
          >
            {user?.firstName?.[0] || user?.email?.[0] || "U"}
          </button>

          {profileOpen && (
            <div className="absolute right-0 top-10 w-56 rounded-lg border bg-popover p-2 shadow-lg">
              <div className="border-b px-2 py-2">
                <p className="text-sm font-medium">
                  {user?.firstName} {user?.lastName}
                </p>
                <p className="text-xs text-muted-foreground">{user?.email}</p>
              </div>
              <div className="mt-1 space-y-1">
                <Link
                  to="/settings/ai-personality"
                  onClick={() => setProfileOpen(false)}
                  className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
                >
                  <Settings className="h-4 w-4" /> Settings
                </Link>
                <Link
                  to="/team"
                  onClick={() => setProfileOpen(false)}
                  className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
                >
                  <User className="h-4 w-4" /> Profile
                </Link>
                <button
                  onClick={() => {
                    setProfileOpen(false);
                    logout();
                  }}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-rose-500 hover:bg-rose-50"
                >
                  <LogOut className="h-4 w-4" /> Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
