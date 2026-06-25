import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useForgotPassword() {
  return useMutation({
    mutationFn: async (email: string) => {
      const response = await api.post("/auth/forgot-password", { email });
      return response.data;
    },
  });
}

export function useResetPassword() {
  return useMutation({
    mutationFn: async (data: { token: string; password: string }) => {
      const response = await api.post("/auth/reset-password", data);
      return response.data;
    },
  });
}
