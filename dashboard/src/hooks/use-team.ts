import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { TeamMember } from "@/types/team";

export function useTeamMembers() {
  return useQuery<TeamMember[]>({
    queryKey: ["team", "members"],
    queryFn: async () => {
      const response = await api.get<TeamMember[]>("/team/members");
      return response.data;
    },
    staleTime: 300000,
  });
}

export function useInviteMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (data: { email: string; role: string }) => {
      const response = await api.post("/team/invite", data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team", "members"] });
    },
  });
}
