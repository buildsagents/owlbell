import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { DEMO_MESSAGES, shouldUseDemoData } from "@/lib/demo-data";
import type { Message, MessageFilters } from "@/types/message";

export function useMessages(filters: MessageFilters = {}) {
  return useQuery<Message[]>({
    queryKey: ["messages", "list", filters],
    queryFn: async () => {
      try {
        const params = new URLSearchParams();
        if (filters.status) params.set("status", filters.status);
        if (filters.priority) params.set("priority", filters.priority);
        if (filters.search) params.set("search", filters.search);
        const response = await api.get<Message[]>(`/messages?${params.toString()}`);
        return response.data;
      } catch {
        if (!shouldUseDemoData()) throw new Error("Messages unavailable");
        let rows = DEMO_MESSAGES;
        if (filters.status) rows = rows.filter((m) => m.status === filters.status);
        if (filters.priority) rows = rows.filter((m) => m.priority === filters.priority);
        if (filters.search) {
          const q = filters.search.toLowerCase();
          rows = rows.filter(
            (m) =>
              m.body.toLowerCase().includes(q) ||
              (m.subject || "").toLowerCase().includes(q) ||
              (m.callerName || "").toLowerCase().includes(q) ||
              m.callerNumber.includes(q),
          );
        }
        return rows;
      }
    },
    staleTime: 30000,
  });
}

export function useUpdateMessageStatus(messageId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (status: string) => {
      const response = await api.patch<Message>(`/messages/${messageId}`, { status });
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["messages"] });
    },
  });
}