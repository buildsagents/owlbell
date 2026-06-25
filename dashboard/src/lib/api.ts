import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/stores/auth-store";
import { queryClient } from "@/lib/query-client";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

// The backend returns snake_case JSON, but the frontend types/components use
// camelCase. Convert all response payloads (from this `api` instance) so the two
// sides line up. The raw axios.post used for token refresh below intentionally
// bypasses this and reads snake_case directly.
function snakeToCamelKey(key: string): string {
  return key.replace(/_([a-z0-9])/g, (_m, c: string) => c.toUpperCase());
}

// Convert camelCase keys to snake_case for request payloads so the backend
// (which uses snake_case) receives properly formatted keys.
function camelToSnakeKey(key: string): string {
  return key.replace(/[A-Z0-9]/g, (c) => `_${c.toLowerCase()}`);
}

function keysToSnake(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(keysToSnake);
  if (value !== null && typeof value === "object" && !(value instanceof Date)) {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([k, v]) => [
        camelToSnakeKey(k),
        keysToSnake(v),
      ])
    );
  }
  return value;
}

function keysToCamel(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(keysToCamel);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([k, v]) => [
        snakeToCamelKey(k),
        keysToCamel(v),
      ])
    );
  }
  return value;
}

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

function addRefreshSubscriber(cb: (token: string) => void) {
  refreshSubscribers.push(cb);
}

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    const tenant = useAuthStore.getState().tenant;
    if (tenant && config.headers) {
      config.headers["X-Tenant-ID"] = tenant.id;
    }
    // Convert request body keys from camelCase to snake_case for backend
    if (config.data && ["post", "put", "patch"].includes(config.method?.toLowerCase() ?? "")) {
      config.data = keysToSnake(config.data);
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => {
    if (response.data && typeof response.data === "object") {
      let body = keysToCamel(response.data) as Record<string, unknown>;
      // Unwrap the standard { success, data, meta } envelope so callers can use
      // response.data directly as the payload (previously every hook saw the
      // envelope and read fields off the wrong level, rendering empty UI).
      if (body && typeof body === "object" && "success" in body && "data" in body) {
        body = body.data as Record<string, unknown>;
      }
      response.data = body;
    }
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (!originalRequest) {
      return Promise.reject(error);
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve) => {
          addRefreshSubscriber((token: string) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            resolve(api(originalRequest));
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshToken = useAuthStore.getState().tokens?.refreshToken;
        if (!refreshToken) {
          throw new Error("No refresh token");
        }

        const response = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token, refresh_token } = response.data.data;

        useAuthStore.getState().setTokens({
          accessToken: access_token,
          refreshToken: refresh_token,
          expiresIn: response.data.data.expires_in,
        });

        onRefreshed(access_token);

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
        }
        return api(originalRequest);
      } catch (refreshError) {
        useAuthStore.getState().logout();
        queryClient.clear();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    if (error.response?.status === 403) {
      console.warn("Permission denied:", originalRequest.url);
    }

    return Promise.reject(error);
  }
);

export async function apiRequest<T>(
  method: "get" | "post" | "put" | "patch" | "delete",
  url: string,
  data?: unknown,
  config?: Record<string, unknown>
): Promise<T> {
  const response = await api.request<T>({
    method,
    url,
    data,
    ...config,
  });
  // The response interceptor already unwraps the envelope to the payload.
  return response.data as T;
}
