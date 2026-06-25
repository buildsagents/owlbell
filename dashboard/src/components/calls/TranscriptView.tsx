import { cn } from "@/lib/utils";
import type { TranscriptSegment } from "@/types/call";
import { Bot, User } from "lucide-react";

interface TranscriptViewProps {
  segments: TranscriptSegment[];
  currentTime?: number;
}

export function TranscriptView({ segments, currentTime }: TranscriptViewProps) {
  return (
    <div className="space-y-3">
      {segments.map((segment) => {
        const isActive =
          currentTime !== undefined &&
          currentTime >= segment.startTime &&
          currentTime <= segment.endTime;

        return (
          <div
            key={segment.id}
            className={cn(
              "flex gap-3 rounded-lg p-3 transition-colors",
              isActive ? "bg-primary/5 border border-primary/20" : "bg-card"
            )}
          >
            <div
              className={cn(
                "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                segment.speaker === "ai"
                  ? "bg-primary/10 text-primary"
                  : "bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300"
              )}
            >
              {segment.speaker === "ai" ? (
                <Bot className="h-4 w-4" />
              ) : (
                <User className="h-4 w-4" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-semibold uppercase">
                  {segment.speaker}
                </span>
                <span className="text-xs text-muted-foreground">
                  {Math.floor(segment.startTime / 60)}:{(segment.startTime % 60).toString().padStart(2, "0")}
                </span>
              </div>
              <p className="text-sm leading-relaxed">{segment.text}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
