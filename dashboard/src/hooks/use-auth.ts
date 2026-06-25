import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { AxiosError } from "axios";
import { useAuthStore } from "@/stores/auth-store";
import { api } from "@/lib/api";
import { queryClient } from "@/lib/query-client";
import type { LoginCredentials, SignupData, ApiError, AuthTokens, User, Tenant } from "@/types";

interface LoginResponse {
  tokens: AuthTokens;
  user: User;
  tenant: Tenant;
}

export function useAuth() {
  const navigate = useNavigate();
  const { user, tenant, isAuthenticated, login: storeLogin, logout: storeLogout } = useAuthStore();

  const login = useMutation({
    mutationFn: async (credentials: LoginCredentials) => {
      const response = await api.post("/auth/login", credentials);
      // The api response interceptor already unwraps the { success, data, meta }
      // envelope, so response.data is the { tokens, user, tenant } payload.
      return response.data as LoginResponse;
    },
    onSuccess: (data) => {
      storeLogin(data.tokens, data.user, data.tenant);
      navigate("/dashboard");
    },
    onError: (error: AxiosError<ApiError>) => {
      console.error("Login failed:", error.response?.data?.error?.message || error.message);
    },
  });

  const signup = useMutation({
    mutationFn: async (data: SignupData) => {
      const response = await api.post<LoginResponse>("/auth/signup", data);
      return response.data;
    },
    onSuccess: (data) => {
      storeLogin(data.tokens, data.user, data.tenant);
      navigate("/dashboard");
    },
    onError: (error: AxiosError<ApiError>) => {
      console.error("Signup failed:", error.response?.data?.error?.message || error.message);
    },
  });

  const logout = useMutation({
    mutationFn: async () => {
      await api.post("/auth/logout");
    },
    onSettled: () => {
      storeLogout();
      queryClient.clear();
      window.location.href = "/login";
    },
  });

  return {
    user,
    tenant,
    isAuthenticated,
    isLoading: login.isPending || signup.isPending,
    login: login.mutate,
    signup: signup.mutate,
    logout: logout.mutate,
    isLoggingOut: logout.isPending,
  };
}
