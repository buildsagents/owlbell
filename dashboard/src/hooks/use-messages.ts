import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Message, MessageFilters } from "@/types/message";

export function useMessages(filters: MessageFilters = {}) {
  return useQuery<Message[]>({
    queryKey: ["messages", "list", filters],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (filters.status) params.set("status", filters.status);
      if (filters.priority) params.set("priority", filters.priority);
      if (filters.search) params.set("search", filters.search);
      const response = await api.get<Message[]>(`/messages?${params.toString()}`);
      return response.data;
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
