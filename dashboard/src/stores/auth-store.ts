import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { User, Tenant, AuthTokens } from "@/types/auth";

interface AuthState {
  user: User | null;
  tenant: Tenant | null;
  tokens: AuthTokens | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  mfaRequired: boolean;
  mfaTempToken: string | null;

  setUser: (user: User) => void;
  setTenant: (tenant: Tenant) => void;
  setTokens: (tokens: AuthTokens) => void;
  setMfaRequired: (required: boolean, tempToken?: string) => void;
  login: (tokens: AuthTokens, user: User, tenant: Tenant) => void;
  logout: () => void;
  setLoading: (loading: boolean) => void;
  updateUser: (updates: Partial<User>) => void;
  getAccessToken: () => string | null;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      tenant: null,
      tokens: null,
      isAuthenticated: false,
      // Auth state is rehydrated synchronously from localStorage, so it is known
      // by first render. Starting "true" left ProtectedRoute spinning forever
      // because nothing resolved it on boot (the infinite-loading glitch).
      isLoading: false,
      mfaRequired: false,
      mfaTempToken: null,

      setUser: (user) => set({ user }),
      setTenant: (tenant) => set({ tenant }),
      setTokens: (tokens) => set({ tokens }),
      setMfaRequired: (required, tempToken) =>
        set({ mfaRequired: required, mfaTempToken: tempToken || null }),
      login: (tokens, user, tenant) =>
        set({
          tokens,
          user,
          tenant,
          isAuthenticated: true,
          isLoading: false,
          mfaRequired: false,
          mfaTempToken: null,
        }),
      logout: () =>
        set({
          user: null,
          tenant: null,
          tokens: null,
          isAuthenticated: false,
          isLoading: false,
          mfaRequired: false,
          mfaTempToken: null,
        }),
      setLoading: (loading) => set({ isLoading: loading }),
      updateUser: (updates) =>
        set((state) => ({
          user: state.user ? { ...state.user, ...updates } : null,
        })),
      getAccessToken: () => get().tokens?.accessToken || null,
    }),
    {
      name: "answerflow_auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        tokens: state.tokens,
        user: state.user,
        tenant: state.tenant,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
