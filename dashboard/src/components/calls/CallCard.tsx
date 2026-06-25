import { Link } from "react-router-dom";
import { cn, formatDuration, formatRelative, formatPhoneNumber } from "@/lib/utils";
import type { Call } from "@/types/call";
import { Phone, PhoneIncoming, PhoneOutgoing, Voicemail, CheckCircle2, XCircle, ArrowUpRight } from "lucide-react";

interface CallCardProps {
  call: Call;
  compact?: boolean;
}

const statusConfig: Record<string, { icon: React.ComponentType<{className?: string}>; color: string; bg: string }> = {
  in_progress: { icon: Phone, color: "text-emerald-500", bg: "bg-emerald-50 dark:bg-emerald-950" },
  ringing: { icon: Phone, color: "text-amber-500", bg: "bg-amber-50 dark:bg-amber-950" },
  completed: { icon: CheckCircle2, color: "text-emerald-500", bg: "bg-emerald-50 dark:bg-emerald-950" },
  missed: { icon: XCircle, color: "text-rose-500", bg: "bg-rose-50 dark:bg-rose-950" },
  voicemail: { icon: Voicemail, color: "text-blue-500", bg: "bg-blue-50 dark:bg-blue-950" },
  transferred: { icon: ArrowUpRight, color: "text-purple-500", bg: "bg-purple-50 dark:bg-purple-950" },
  failed: { icon: XCircle, color: "text-rose-500", bg: "bg-rose-50 dark:bg-rose-950" },
};

export function CallCard({ call, compact }: CallCardProps) {
  const config = statusConfig[call.status] || statusConfig.completed;
  const StatusIcon = config.icon;

  return (
    <Link
      to={`/calls/${call.id}`}
      className={cn(
        "group flex items-center gap-3 rounded-lg border bg-card p-3 transition-all hover:shadow-sm",
        compact ? "py-2" : "py-3"
      )}
    >
      <div className={cn("flex h-10 w-10 items-center justify-center rounded-full", config.bg)}>
        {call.direction === "inbound" ? (
          <PhoneIncoming className={cn("h-4 w-4", config.color)} />
        ) : (
          <PhoneOutgoing className={cn("h-4 w-4", config.color)} />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium truncate">
            {call.callerName || formatPhoneNumber(call.callerNumber)}
          </span>
          <StatusIcon className={cn("h-3.5 w-3.5", config.color)} />
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{formatDuration(call.duration)}</span>
          <span>•</span>
          <span>{formatRelative(call.createdAt)}</span>
        </div>
      </div>
      {!compact && call.outcome && (
        <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium capitalize">
          {call.outcome.replace(/_/g, " ")}
        </span>
      )}
    </Link>
  );
}
