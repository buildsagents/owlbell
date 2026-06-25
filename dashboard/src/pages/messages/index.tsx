import { useState } from "react";
import { useMessages, useUpdateMessageStatus } from "@/hooks/use-messages";
import { PageHeader } from "@/components/layout/PageHeader";
import { MessageCard } from "@/components/messages/MessageCard";
import { EmptyState } from "@/components/shared/empty-state";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useDebounce } from "@/hooks/use-debounce";
import { cn, formatRelative } from "@/lib/utils";
import type { MessageStatus } from "@/types/message";
import { MessageSquare, Search, X, Phone, User, CheckCircle2, Archive } from "lucide-react";

const STATUSES: MessageStatus[] = ["new", "in_progress", "resolved", "archived"];

export default function MessagesPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<MessageStatus | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const debouncedSearch = useDebounce(search, 300);

  const { data: messages, isLoading, isError, refetch } = useMessages({
    status,
    search: debouncedSearch,
  });

  const selectedMessage = messages?.find((m) => m.id === selectedId) || null;

  return (
    <div className="space-y-6">
      <PageHeader title="Messages" description="AI-taken messages from your callers" />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search messages..." value={search} onChange={(e) => setSearch(e.target.value)} className="pl-9" />
          {search && <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2"><X className="h-4 w-4" /></button>}
        </div>
        <div className="flex gap-2">
          {STATUSES.map((s) => (
            <button
              key={s}
              onClick={() => setStatus(status === s ? null : s)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium capitalize transition-colors",
                status === s ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-accent"
              )}
            >
              {s.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Message List */}
        <div className="lg:col-span-1 space-y-2 max-h-[600px] overflow-y-auto">
          {isLoading ? <LoadingSpinner /> : isError ? <ErrorState onRetry={refetch} /> : messages && messages.length > 0 ? (
            messages.map((msg) => (
              <MessageCard key={msg.id} message={msg} selected={selectedId === msg.id} onClick={() => setSelectedId(msg.id)} />
            ))
          ) : (
            <EmptyState title="No messages" description="Messages from callers will appear here." icon={MessageSquare} />
          )}
        </div>

        {/* Message Detail */}
        <div className="lg:col-span-2">
          {selectedMessage ? (
            <MessageDetail message={selectedMessage} />
          ) : (
            <div className="flex h-full items-center justify-center rounded-lg border border-dashed">
              <p className="text-muted-foreground">Select a message to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MessageDetail({ message }: { message: import("@/types/message").Message }) {
  const updateStatus = useUpdateMessageStatus(message.id);

  const statusColors: Record<string, string> = {
    new: "bg-blue-100 text-blue-700",
    in_progress: "bg-amber-100 text-amber-700",
    resolved: "bg-emerald-100 text-emerald-700",
    archived: "bg-muted text-muted-foreground",
  };

  return (
    <div className="rounded-lg border bg-card">
      <div className="border-b p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Badge className={statusColors[message.status]}>{message.status.replace("_", " ")}</Badge>
            <Badge variant="outline" className="capitalize">{message.priority}</Badge>
          </div>
          <span className="text-xs text-muted-foreground">{formatRelative(message.createdAt)}</span>
        </div>
        <h3 className="mt-2 text-lg font-semibold">{message.subject || "No Subject"}</h3>
        <div className="mt-1 flex items-center gap-3 text-sm text-muted-foreground">
          <span className="flex items-center gap-1"><User className="h-3 w-3" /> {message.callerName || "Unknown"}</span>
          <span className="flex items-center gap-1"><Phone className="h-3 w-3" /> {message.callerNumber}</span>
        </div>
      </div>
      <div className="p-4">
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.body}</p>
      </div>
      <div className="border-t p-4 flex gap-2">
        {message.status !== "resolved" && (
          <Button size="sm" onClick={() => updateStatus.mutate("resolved")}>
            <CheckCircle2 className="mr-1 h-4 w-4" /> Mark Resolved
          </Button>
        )}
        {message.status !== "archived" && (
          <Button variant="outline" size="sm" onClick={() => updateStatus.mutate("archived")}>
            <Archive className="mr-1 h-4 w-4" /> Archive
          </Button>
        )}
      </div>
    </div>
  );
}
