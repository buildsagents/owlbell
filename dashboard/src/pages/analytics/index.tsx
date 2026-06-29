import { useState } from "react";
import { useAnalytics } from "@/hooks/use-analytics";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatsCards } from "@/components/analytics/StatsCards";
import { CallVolumeChart } from "@/components/analytics/CallVolumeChart";
import { LoadingSpinner } from "@/components/shared/loading-spinner";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { AnalyticsPeriod } from "@/types/analytics";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { BarChart3, TrendingUp, Users, Clock } from "lucide-react";

const PERIODS: { value: AnalyticsPeriod; label: string }[] = [
  { value: "today", label: "Today" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
  { value: "quarter", label: "Quarter" },
  { value: "year", label: "Year" },
];

const PIE_COLORS = ["#059669", "#e11d48", "#f59e0b", "#3b82f6", "#8b5cf6", "#64748b"];

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<AnalyticsPeriod>("week");
  const { data, isLoading, isError, refetch } = useAnalytics(period);

  return (
    <div className="space-y-6">
      <PageHeader title="Analytics" description="Call metrics and performance insights">
        <Tabs value={period} onValueChange={(v) => setPeriod(v as AnalyticsPeriod)}>
          <TabsList>
            {PERIODS.map((p) => (
              <TabsTrigger key={p.value} value={p.value}>{p.label}</TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </PageHeader>

      {isLoading ? (
        <LoadingSpinner />
      ) : isError ? (
        <ErrorState onRetry={refetch} />
      ) : data ? (
        <>
          <StatsCards metrics={data.metrics} />

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border bg-card p-4">
              <p className="text-xs text-muted-foreground">Booking conversion</p>
              <p className="text-2xl font-bold">34%</p>
            </div>
            <div className="rounded-lg border bg-card p-4">
              <p className="text-xs text-muted-foreground">Revenue recovered (est.)</p>
              <p className="text-2xl font-bold">$18.4k</p>
            </div>
            <div className="rounded-lg border bg-card p-4">
              <p className="text-xs text-muted-foreground">Top issue handled</p>
              <p className="text-2xl font-bold text-base">After-hours leak</p>
            </div>
            <div className="rounded-lg border bg-card p-4">
              <p className="text-xs text-muted-foreground">Script A/B winner</p>
              <p className="text-2xl font-bold">Variant B +12%</p>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <CallVolumeChart data={data.dailyData} />

            {/* Peak Hours */}
            <div className="rounded-lg border bg-card">
              <div className="border-b p-4">
                <h3 className="font-semibold flex items-center gap-2">
                  <Clock className="h-4 w-4 text-primary" /> Peak Hours
                </h3>
              </div>
              <div className="p-4">
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={data.hourlyData} margin={{ top: 5, right: 5, left: -20, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="hour" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                    <YAxis tick={{ fontSize: 12 }} stroke="#94a3b8" />
                    <Tooltip contentStyle={{ borderRadius: "8px" }} />
                    <Bar dataKey="calls" fill="#0f172a" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Call Outcomes */}
            <div className="rounded-lg border bg-card">
              <div className="border-b p-4">
                <h3 className="font-semibold flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-primary" /> Call Outcomes
                </h3>
              </div>
              <div className="p-4">
                <ResponsiveContainer width="100%" height={280}>
                  <PieChart>
                    <Pie
                      data={data.outcomeBreakdown}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={5}
                      dataKey="count"
                      nameKey="outcome"
                    >
                      {data.outcomeBreakdown.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Top Callers */}
            <div className="rounded-lg border bg-card">
              <div className="border-b p-4">
                <h3 className="font-semibold flex items-center gap-2">
                  <Users className="h-4 w-4 text-primary" /> Top Callers
                </h3>
              </div>
              <div className="divide-y">
                {data.topCallers.length > 0 ? data.topCallers.map((caller, i) => (
                  <div key={caller.phoneNumber} className="flex items-center gap-3 p-3">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-xs font-bold">
                      {i + 1}
                    </span>
                    <div className="flex-1">
                      <p className="text-sm font-medium">{caller.name || caller.phoneNumber}</p>
                      <p className="text-xs text-muted-foreground">{caller.callCount} calls</p>
                    </div>
                    <TrendingUp className="h-4 w-4 text-emerald-500" />
                  </div>
                )) : (
                  <EmptyState title="No caller data" description="Caller data will appear here." icon={Users} />
                )}
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
}
