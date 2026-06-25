import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { AiSettings, FaqEntry, KnowledgeDocument } from "@/types/settings";

export function useAISettings() {
  return useQuery<AiSettings>({
    queryKey: ["settings", "ai"],
    queryFn: async () => {
      const response = await api.get<AiSettings>("/settings/ai");
      return response.data;
    },
    staleTime: 300000,
  });
}

export function useUpdateAISettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: Partial<AiSettings>) => {
      const response = await api.patch<AiSettings>("/settings/ai", data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings", "ai"] });
    },
  });
}

export function useFaqEntries() {
  return useQuery<FaqEntry[]>({
    queryKey: ["settings", "faqs"],
    queryFn: async () => {
      const response = await api.get<FaqEntry[]>("/settings/faqs");
      return response.data;
    },
    staleTime: 300000,
  });
}

export function useKnowledgeDocuments() {
  return useQuery<KnowledgeDocument[]>({
    queryKey: ["knowledge", "documents"],
    queryFn: async () => {
      const response = await api.get<KnowledgeDocument[]>("/knowledge/documents");
      return response.data;
    },
    staleTime: 300000,
  });
}
