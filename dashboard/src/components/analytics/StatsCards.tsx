import { Card, CardContent } from "@/components/ui/card";
import { cn, formatDuration, formatChange } from "@/lib/utils";
import type { CallMetrics } from "@/types/analytics";
import {
  Phone,
  PhoneCall,
  PhoneMissed,
  Clock,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";

interface StatsCardsProps {
  metrics: CallMetrics;
}

interface StatItem {
  label: string;
  value: string | number;
  change: number;
  changeLabel?: string;
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
}

export function StatsCards({ metrics }: StatsCardsProps) {
  const stats: StatItem[] = [
    {
      label: "Total Calls",
      value: metrics.totalCalls,
      change: metrics.totalChange,
      icon: Phone,
      iconColor: "text-blue-500",
    },
    {
      label: "Answered",
      value: metrics.answeredCalls,
      change: metrics.answeredChange,
      icon: PhoneCall,
      iconColor: "text-emerald-500",
    },
    {
      label: "Missed",
      value: metrics.missedCalls,
      change: metrics.missedChange,
      icon: PhoneMissed,
      iconColor: "text-rose-500",
    },
    {
      label: "Avg Duration",
      value: formatDuration(metrics.avgDuration),
      change: metrics.avgDurationChange,
      icon: Clock,
      iconColor: "text-amber-500",
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {stats.map((stat) => {
        const Icon = stat.icon;
        const TrendIcon = stat.change > 0 ? TrendingUp : stat.change < 0 ? TrendingDown : Minus;
        const trendColor =
          stat.change > 0
            ? "text-emerald-500"
            : stat.change < 0
            ? "text-rose-500"
            : "text-muted-foreground";

        return (
          <Card key={stat.label}>
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div className={cn("rounded-lg p-2", stat.iconColor.replace("text-", "bg-").replace("500", "50"))}>
                  <Icon className={cn("h-5 w-5", stat.iconColor)} />
                </div>
                <div className="flex items-center gap-1 text-xs font-medium">
                  <TrendIcon className={cn("h-3 w-3", trendColor)} />
                  <span className={trendColor}>{formatChange(stat.change)}</span>
                </div>
              </div>
              <div className="mt-4">
                <p className="text-2xl font-bold tabular-nums">{stat.value}</p>
                <p className="text-sm text-muted-foreground">{stat.label}</p>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
