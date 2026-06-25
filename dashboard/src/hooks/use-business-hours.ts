import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useBusinessHours() {
  return useQuery({
    queryKey: ["business-hours"],
    queryFn: async () => {
      const response = await api.get("/appointments/business-hours/config");
      return response.data;
    },
  });
}

export function useUpdateBusinessHours() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: any) => {
      const response = await api.put("/appointments/business-hours/config", data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["business-hours"] });
    },
  });
}
