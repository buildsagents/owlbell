import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Integration } from "@/types/integration";

export function useIntegrations() {
  return useQuery<Integration[]>({
    queryKey: ["integrations"],
    queryFn: async () => {
      const response = await api.get<Integration[]>("/integrations");
      return response.data;
    },
    staleTime: 60000,
  });
}
