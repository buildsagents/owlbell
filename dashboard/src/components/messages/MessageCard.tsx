import { cn, formatRelative, truncate } from "@/lib/utils";
import type { Message } from "@/types/message";
import { Mail, Phone, AlertCircle } from "lucide-react";

interface MessageCardProps {
  message: Message;
  selected?: boolean;
  onClick?: () => void;
}

const priorityConfig: Record<string, { color: string; icon: React.ComponentType<{className?: string}> }> = {
  urgent: { color: "text-rose-500", icon: AlertCircle },
  high: { color: "text-amber-500", icon: AlertCircle },
  medium: { color: "text-blue-500", icon: Mail },
  low: { color: "text-muted-foreground", icon: Mail },
};

const statusConfig: Record<string, string> = {
  new: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  in_progress: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  resolved: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300",
  archived: "bg-muted text-muted-foreground",
};

export function MessageCard({ message, selected, onClick }: MessageCardProps) {
  const config = priorityConfig[message.priority] || priorityConfig.medium;
  const PriorityIcon = config.icon;

  return (
    <button
      onClick={onClick}
      className={cn(
        "flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-all hover:shadow-sm",
        selected ? "border-primary bg-primary/5" : "bg-card"
      )}
    >
      <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-full", config.color.replace("text-", "bg-").replace("500", "50"))}>
        <PriorityIcon className={cn("h-4 w-4", config.color)} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium truncate">
            {message.callerName || message.callerNumber}
          </span>
          <span className={cn("rounded-full px-1.5 py-0.5 text-[10px] font-medium", statusConfig[message.status])}>
            {message.status.replace("_", " ")}
          </span>
        </div>
        {message.subject && (
          <p className="text-xs font-medium text-foreground truncate">{message.subject}</p>
        )}
        <p className="text-xs text-muted-foreground truncate">{truncate(message.body, 80)}</p>
        <div className="mt-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <Phone className="h-3 w-3" />
          <span>{message.callerNumber}</span>
          <span>•</span>
          <span>{formatRelative(message.createdAt)}</span>
        </div>
      </div>
    </button>
  );
}
