import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AnalyticsResponse, AnalyticsPeriod } from "@/types/analytics";

export function useAnalytics(
  period: AnalyticsPeriod = "week",
  dateRange?: { from: string; to: string }
) {
  return useQuery<AnalyticsResponse>({
    queryKey: ["analytics", period, dateRange],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("period", period);
      if (dateRange) {
        params.set("from", dateRange.from);
        params.set("to", dateRange.to);
      }
      const response = await api.get<AnalyticsResponse>(`/analytics/metrics?${params.toString()}`);
      return response.data;
    },
    staleTime: 1000 * 60 * 5,
  });
}
