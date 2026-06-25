import { create } from "zustand";

export type WSConnectionStatus = "connecting" | "connected" | "disconnected" | "reconnecting" | "error";

interface WebSocketState {
  status: WSConnectionStatus;
  lastConnectedAt: string | null;
  lastDisconnectedAt: string | null;
  reconnectAttempt: number;
  subscribedChannels: string[];

  setStatus: (status: WSConnectionStatus) => void;
  setSubscribedChannels: (channels: string[]) => void;
  addSubscribedChannel: (channel: string) => void;
  removeSubscribedChannel: (channel: string) => void;
  incrementReconnectAttempt: () => void;
  resetReconnectAttempt: () => void;
}

export const useWebSocketStore = create<WebSocketState>()((set) => ({
  status: "disconnected",
  lastConnectedAt: null,
  lastDisconnectedAt: null,
  reconnectAttempt: 0,
  subscribedChannels: [],

  setStatus: (status) =>
    set((state) => ({
      status,
      lastConnectedAt:
        status === "connected" ? new Date().toISOString() : state.lastConnectedAt,
      lastDisconnectedAt:
        status === "disconnected" ? new Date().toISOString() : state.lastDisconnectedAt,
    })),

  setSubscribedChannels: (channels) => set({ subscribedChannels: channels }),
  addSubscribedChannel: (channel) =>
    set((state) => ({
      subscribedChannels: [...state.subscribedChannels, channel],
    })),
  removeSubscribedChannel: (channel) =>
    set((state) => ({
      subscribedChannels: state.subscribedChannels.filter((c) => c !== channel),
    })),
  incrementReconnectAttempt: () =>
    set((state) => ({ reconnectAttempt: state.reconnectAttempt + 1 })),
  resetReconnectAttempt: () => set({ reconnectAttempt: 0 }),
}));
