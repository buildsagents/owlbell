import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { DEMO_CALLS, shouldUseDemoData } from "@/lib/demo-data";
import type { Call, CallsResponse, CallFilters } from "@/types/call";

export function useCalls(
  filters: CallFilters = {},
  pagination: { page: number; pageSize: number } = { page: 1, pageSize: 25 }
) {
  return useQuery<CallsResponse>({
    queryKey: ["calls", "list", filters, pagination],
    queryFn: async () => {
      try {
        const params = new URLSearchParams();
        if (filters.status) params.set("status", filters.status);
        if (filters.direction) params.set("direction", filters.direction);
        if (filters.outcome) params.set("outcome", filters.outcome);
        if (filters.dateFrom) params.set("date_from", filters.dateFrom);
        if (filters.dateTo) params.set("date_to", filters.dateTo);
        if (filters.search) params.set("search", filters.search);
        params.set("page", String(pagination.page));
        params.set("page_size", String(pagination.pageSize));
        const response = await api.get<CallsResponse>(`/calls?${params.toString()}`);
        return response.data;
      } catch {
        if (!shouldUseDemoData()) throw new Error("Calls unavailable");
        let calls = DEMO_CALLS.calls;
        if (filters.search) {
          const q = filters.search.toLowerCase();
          calls = calls.filter(
            (c) =>
              c.callerNumber.includes(q) ||
              (c.callerName || "").toLowerCase().includes(q) ||
              (c.summary || "").toLowerCase().includes(q),
          );
        }
        if (filters.status) calls = calls.filter((c) => c.status === filters.status);
        return { ...DEMO_CALLS, calls, pagination: { ...DEMO_CALLS.pagination, total: calls.length } };
      }
    },
    staleTime: 30000,
  });
}

export function useCallDetail(callId: string | null) {
  return useQuery<Call>({
    queryKey: ["calls", "detail", callId],
    queryFn: async () => {
      if (!callId) throw new Error("No call ID");
      try {
        const response = await api.get<Call>(`/calls/${callId}`);
        return response.data;
      } catch {
        if (!shouldUseDemoData()) throw new Error("Call not found");
        const found = DEMO_CALLS.calls.find((c) => c.id === callId);
        if (!found) throw new Error("Call not found");
        return found;
      }
    },
    enabled: !!callId,
    staleTime: 60000,
  });
}

export function useUpdateCallNotes(callId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (notes: string) => {
      const response = await api.patch<Call>(`/calls/${callId}`, { notes });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calls", "detail", callId] });
    },
  });
}