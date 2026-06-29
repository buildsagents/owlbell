import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { DEMO_ANALYTICS, shouldUseDemoData } from "@/lib/demo-data";
import type { AnalyticsResponse, AnalyticsPeriod } from "@/types/analytics";

export function useAnalytics(
  period: AnalyticsPeriod = "week",
  dateRange?: { from: string; to: string }
) {
  return useQuery<AnalyticsResponse>({
    queryKey: ["analytics", period, dateRange],
    queryFn: async () => {
      try {
        const params = new URLSearchParams();
        params.set("period", period);
        if (dateRange) {
          params.set("from", dateRange.from);
          params.set("to", dateRange.to);
        }
        const response = await api.get<AnalyticsResponse>(`/analytics/metrics?${params.toString()}`);
        return response.data;
      } catch {
        if (shouldUseDemoData()) return { ...DEMO_ANALYTICS, period };
        throw new Error("Analytics unavailable");
      }
    },
    staleTime: 1000 * 60 * 5,
  });
}