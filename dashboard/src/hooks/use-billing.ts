import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { UsageStats } from "@/types/billing";

export function useBillingUsage() {
  return useQuery<UsageStats>({
    queryKey: ["billing", "usage"],
    queryFn: async () => {
      const response = await api.get<UsageStats>("/billing/usage");
      return response.data;
    },
    staleTime: 60000,
  });
}
