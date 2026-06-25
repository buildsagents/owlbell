import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/auth-store";
import { useCallStore } from "@/stores/call-store";
import { useCalls } from "@/hooks/use-calls";
import { useMessages } from "@/hooks/use-messages";
import { useAppointments } from "@/hooks/use-appointments";
import { useAnalytics } from "@/hooks/use-analytics";
import { StatsCards } from "@/components/analytics/StatsCards";
import { CallVolumeChart } from "@/components/analytics/CallVolumeChart";
import { CallCard } from "@/components/calls/CallCard";
import { MessageCard } from "@/components/messages/MessageCard";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/utils";
import {
  Phone,
  MessageSquare,
  CalendarDays,
  Settings,
  Users,
  Zap,
  PhoneCall,
} from "lucide-react";

export default function DashboardPage() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const activeCalls = useCallStore((s) => s.activeCalls);
  const { data: callsData, isLoading: callsLoading } = useCalls({}, { page: 1, pageSize: 5 });
  const { data: messages, isLoading: messagesLoading } = useMessages({});
  useAppointments();
  const { data: analytics } = useAnalytics("week");

  const greeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  };

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="rounded-xl bg-gradient-to-r from-primary to-primary/80 p-6 text-primary-foreground">
        <h1 className="text-2xl font-bold">
          {greeting()}, {user?.firstName || "there"}
        </h1>
        <p className="mt-1 text-primary-foreground/80">
          {formatDate(new Date().toISOString(), "EEEE, MMMM d, yyyy")}
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <div className="flex items-center gap-2 rounded-lg bg-white/10 px-3 py-1.5 text-sm">
            <PhoneCall className="h-4 w-4" />
            <span>{callsData?.summary?.totalCalls ?? 0} calls today</span>
          </div>
          <div className="flex items-center gap-2 rounded-lg bg-white/10 px-3 py-1.5 text-sm">
            <Zap className="h-4 w-4" />
            <span>{activeCalls.length} active</span>
          </div>
        </div>
      </div>

      {/* Active Calls */}
      {activeCalls.length > 0 && (
        <div>
          <h2 className="mb-3 text-lg font-semibold flex items-center gap-2">
            <span className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500" />
            </span>
            Live Calls
          </h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {activeCalls.map((call) => (
              <CallCard key={call.id} call={call} compact />
            ))}
          </div>
        </div>
      )}

      {/* Stats */}
      {analytics?.metrics && <StatsCards metrics={analytics.metrics} />}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Call Volume Chart */}
        {analytics?.dailyData && (
          <CallVolumeChart data={analytics.dailyData} />
        )}

        {/* Recent Calls */}
        <div className="rounded-lg border bg-card">
          <div className="flex items-center justify-between border-b p-4">
            <h3 className="font-semibold flex items-center gap-2">
              <Phone className="h-4 w-4 text-primary" />
              Recent Calls
            </h3>
            <Button variant="ghost" size="sm" onClick={() => navigate("/calls")}>
              View all
            </Button>
          </div>
          <div className="p-4 space-y-2">
            {callsLoading ? (
              <LoadingSpinner />
            ) : callsData?.calls && callsData.calls.length > 0 ? (
              callsData.calls.slice(0, 5).map((call) => (
                <CallCard key={call.id} call={call} compact />
              ))
            ) : (
              <EmptyState title="No calls yet" description="Your call history will appear here." icon={Phone} />
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Messages */}
        <div className="rounded-lg border bg-card">
          <div className="flex items-center justify-between border-b p-4">
            <h3 className="font-semibold flex items-center gap-2">
              <MessageSquare className="h-4 w-4 text-primary" />
              Recent Messages
            </h3>
            <Button variant="ghost" size="sm" onClick={() => navigate("/messages")}>
              View all
            </Button>
          </div>
          <div className="p-4 space-y-2">
            {messagesLoading ? (
              <LoadingSpinner />
            ) : messages && messages.length > 0 ? (
              messages.slice(0, 5).map((msg) => (
                <MessageCard key={msg.id} message={msg} />
              ))
            ) : (
              <EmptyState title="No messages" description="Messages from callers will appear here." icon={MessageSquare} />
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="rounded-lg border bg-card">
          <div className="border-b p-4">
            <h3 className="font-semibold">Quick Actions</h3>
          </div>
          <div className="p-4 grid grid-cols-2 gap-3">
            <QuickAction
              icon={Settings}
              label="Customize AI"
              desc="Voice, persona, greeting"
              onClick={() => navigate("/settings/ai-personality")}
            />
            <QuickAction
              icon={Users}
              label="Add Team Member"
              desc="Invite colleagues"
              onClick={() => navigate("/team")}
            />
            <QuickAction
              icon={CalendarDays}
              label="View Appointments"
              desc="AI-booked meetings"
              onClick={() => navigate("/appointments")}
            />
            <QuickAction
              icon={Zap}
              label="Connect Integration"
              desc="Google, Slack, CRM"
              onClick={() => navigate("/settings/integrations")}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function QuickAction({
  icon: Icon,
  label,
  desc,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  desc: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-start gap-2 rounded-lg border p-4 text-left transition-all hover:bg-accent"
    >
      <Icon className="h-5 w-5 text-primary" />
      <div>
        <p className="text-sm font-medium">{label}</p>
        <p className="text-xs text-muted-foreground">{desc}</p>
      </div>
    </button>
  );
}
