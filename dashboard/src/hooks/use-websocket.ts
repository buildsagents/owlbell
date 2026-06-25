import { useEffect, useCallback } from "react";
import { wsClient } from "@/lib/websocket";
import { useAuthStore } from "@/stores/auth-store";
import { useWebSocketStore } from "@/stores/websocket-store";

export function useWebSocket() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const status = useWebSocketStore((s) => s.status);

  const connect = useCallback(() => {
    if (isAuthenticated) {
      wsClient.connect();
    }
  }, [isAuthenticated]);

  const disconnect = useCallback(() => {
    wsClient.disconnect();
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      connect();
    } else {
      disconnect();
    }
    return () => disconnect();
  }, [isAuthenticated, connect, disconnect]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible" && isAuthenticated) {
        const state = useWebSocketStore.getState();
        if (state.status === "disconnected" || state.status === "error") {
          connect();
        }
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () =>
      document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, [isAuthenticated, connect]);

  return {
    status,
    isConnected: status === "connected",
    connect,
    disconnect,
  };
}
