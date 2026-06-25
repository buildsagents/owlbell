import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Appointment } from "@/types/appointment";

export function useAppointments(dateFrom?: string, dateTo?: string) {
  return useQuery<Appointment[]>({
    queryKey: ["appointments", dateFrom, dateTo],
    queryFn: async () => {
      const params = new URLSearchParams();
      if (dateFrom) params.set("from", dateFrom);
      if (dateTo) params.set("to", dateTo);
      const response = await api.get<Appointment[]>(`/appointments?${params.toString()}`);
      return response.data;
    },
    staleTime: 60000,
  });
}
