import { useParams, useNavigate } from "react-router-dom";
import { useState, useCallback } from "react";
import { useCallDetail, useUpdateCallNotes } from "@/hooks/use-calls";
import { PageHeader } from "@/components/layout/PageHeader";
import { CallPlayer } from "@/components/calls/CallPlayer";
import { TranscriptView } from "@/components/calls/TranscriptView";
import { CallSummary } from "@/components/calls/CallSummary";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn, formatDate, formatDuration, formatPhoneNumber } from "@/lib/utils";
import { ArrowLeft, Phone, Clock, MapPin, Tag, FileText } from "lucide-react";

export default function CallDetailPage() {
  const { callId } = useParams<{ callId: string }>();
  const navigate = useNavigate();
  const { data: call, isLoading, isError, refetch } = useCallDetail(callId || null);
  const updateNotes = useUpdateCallNotes(callId || "");
  const [currentTime, setCurrentTime] = useState(0);
  const [notes, setNotes] = useState("");

  const handleTimeUpdate = useCallback((time: number) => {
    setCurrentTime(time);
  }, []);

  const handleNotesBlur = () => {
    if (callId && notes !== call?.notes) {
      updateNotes.mutate(notes);
    }
  };

  if (isLoading) return <LoadingSpinner className="py-12" />;
  if (isError || !call) return <ErrorState onRetry={refetch} />;

  const statusColor: Record<string, string> = {
    completed: "bg-emerald-100 text-emerald-700",
    missed: "bg-rose-100 text-rose-700",
    voicemail: "bg-blue-100 text-blue-700",
    transferred: "bg-purple-100 text-purple-700",
    in_progress: "bg-amber-100 text-amber-700",
    ringing: "bg-amber-100 text-amber-700",
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Call Detail">
        <Button variant="outline" size="sm" onClick={() => navigate("/calls")}>
          <ArrowLeft className="mr-1 h-4 w-4" /> Back
        </Button>
      </PageHeader>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left: Call Info */}
        <div className="space-y-4 lg:col-span-1">
          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">Call Information</h3>
              <Badge className={cn(statusColor[call.status] || "bg-muted")}>
                {call.status}
              </Badge>
            </div>
            <div className="space-y-3">
              <InfoRow icon={Phone} label="Caller" value={call.callerName || formatPhoneNumber(call.callerNumber)} />
              <InfoRow icon={Phone} label="Number" value={formatPhoneNumber(call.callerNumber)} />
              <InfoRow icon={Clock} label="Duration" value={formatDuration(call.duration)} />
              <InfoRow icon={MapPin} label="Direction" value={call.direction} />
              {call.outcome && <InfoRow icon={Tag} label="Outcome" value={call.outcome.replace(/_/g, " ")} />}
              <InfoRow icon={Clock} label="Started" value={formatDate(call.startedAt, "MMM d, yyyy h:mm a")} />
              {call.aiAgentName && <InfoRow icon={FileText} label="Receptionist" value={call.aiAgentName} />}
            </div>
            {call.tags.length > 0 && (
              <div className="mt-4 flex flex-wrap gap-1">
                {call.tags.map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
                ))}
              </div>
            )}
          </div>

          {/* Notes */}
          <div className="rounded-lg border bg-card p-4">
            <h3 className="mb-3 font-semibold">Notes</h3>
            <textarea
              value={notes || call.notes || ""}
              onChange={(e) => setNotes(e.target.value)}
              onBlur={handleNotesBlur}
              placeholder="Add notes about this call..."
              className="min-h-[100px] w-full rounded-md border bg-transparent px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/20 resize-none"
            />
          </div>

          {/* Summary */}
          {call.summary && <CallSummary summary={call.summary} />}
        </div>

        {/* Right: Audio + Transcript */}
        <div className="space-y-4 lg:col-span-2">
          {call.recordingUrl && (
            <CallPlayer audioUrl={call.recordingUrl} onTimeUpdate={handleTimeUpdate} />
          )}
          {call.transcript && call.transcript.length > 0 && (
            <div className="rounded-lg border bg-card p-4">
              <h3 className="mb-4 font-semibold">Transcript</h3>
              <TranscriptView segments={call.transcript} currentTime={currentTime} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function InfoRow({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-2">
      <Icon className="mt-0.5 h-4 w-4 text-muted-foreground" />
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-medium capitalize">{value}</p>
      </div>
    </div>
  );
}
