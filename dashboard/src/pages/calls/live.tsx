import { useMemo, useState } from "react";
import { useCalls } from "@/hooks/use-calls";
import { useDemoLiveFeed } from "@/hooks/use-demo-live-feed";
import { useWebSocket } from "@/hooks/use-websocket";
import { useCallStore } from "@/stores/call-store";
import { wsClient } from "@/lib/websocket";
import { PageHeader } from "@/components/layout/PageHeader";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Headphones, Radio, MessageSquare } from "lucide-react";

export default function LiveCallsPage() {
  const { isConnected } = useWebSocket();
  const { data, isLoading } = useCalls({ status: "in_progress" }, { page: 1, pageSize: 10 });
  const demoFeed = useDemoLiveFeed();
  const activeCalls = useCallStore((s) => s.activeCalls);
  const [listeningId, setListeningId] = useState<string | null>(null);

  const liveCalls = useMemo(() => {
    const fromApi =
      data?.calls.filter((c) => c.status === "in_progress" || c.status === "ringing") ?? [];
    const merged = [...activeCalls, ...fromApi];
    const seen = new Set<string>();
    const real = merged.filter((c) => {
      if (seen.has(c.id)) return false;
      seen.add(c.id);
      return true;
    });
    if (real.length > 0) return real;
    return demoFeed.calls;
  }, [data, activeCalls, demoFeed.calls]);

  const showingDemo = liveCalls.length > 0 && liveCalls[0]?.id.startsWith("demo-call");

  const onListen = (callId: string) => {
    wsClient.listenToCall(callId);
    setListeningId(callId);
    toast.message("Listening in", {
      description: showingDemo
        ? "Demo feed — transcript updates every few seconds."
        : `Subscribed to live audio for call ${callId.slice(0, 8)}…`,
    });
  };

  const onTakeover = (callId: string) => {
    wsClient.takeOverCall(callId);
    toast.message("Takeover requested", { description: "AI will transfer control to your line." });
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Live monitoring" description="Listen in, view AI reasoning, and intervene when needed">
        <div className="flex items-center gap-2 text-sm">
          <span className={`h-2 w-2 rounded-full ${isConnected ? "bg-emerald-500" : "bg-amber-500"}`} />
          {isConnected ? "WebSocket connected" : "Connecting…"}
          {showingDemo && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-900 dark:bg-amber-950 dark:text-amber-100">
              Demo live feed
            </span>
          )}
        </div>
      </PageHeader>

      {isLoading ? (
        <LoadingSpinner />
      ) : liveCalls.length === 0 ? (
        <div className="rounded-lg border bg-card p-8 text-center">
          <Radio className="mx-auto h-8 w-8 text-muted-foreground" />
          <p className="mt-3 font-medium">No active calls right now</p>
          <p className="text-sm text-muted-foreground">Place a test call from onboarding to see live transcripts here.</p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {liveCalls.map((call) => {
            const reasoning =
              "reasoning" in call && typeof call.reasoning === "string"
                ? call.reasoning
                : "Qualify urgency → capture address → offer next slot";
            return (
              <article key={call.id} className="rounded-lg border bg-card p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold">{call.callerName || call.callerNumber}</p>
                    <p className="text-xs text-muted-foreground">
                      {call.aiAgentName} · {call.status}
                    </p>
                  </div>
                  {listeningId === call.id && (
                    <span className="text-xs font-medium text-emerald-600">Listening</span>
                  )}
                </div>
                <div className="mt-4 max-h-48 overflow-y-auto rounded-md bg-muted/40 p-3 text-sm">
                  {(call.transcript || []).map((seg) => (
                    <p key={seg.id} className={seg.speaker === "ai" ? "text-primary" : ""}>
                      <strong>{seg.speaker === "ai" ? "AI" : "Caller"}:</strong> {seg.text}
                    </p>
                  ))}
                </div>
                <p className="mt-3 text-xs text-muted-foreground">
                  <MessageSquare className="mr-1 inline h-3 w-3" />
                  Reasoning: {reasoning}
                </p>
                <div className="mt-4 flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => onListen(call.id)}>
                    <Headphones className="mr-1 h-4 w-4" /> Listen in
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => onTakeover(call.id)}>
                    Take over
                  </Button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}