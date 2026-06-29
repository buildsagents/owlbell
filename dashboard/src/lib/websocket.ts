import { useAuthStore } from "@/stores/auth-store";
import { useWebSocketStore } from "@/stores/websocket-store";
import { useCallStore } from "@/stores/call-store";
import { useNotificationStore } from "@/stores/notification-store";
import type { WebSocketMessage, TranscriptSegment, ActiveCall, Notification } from "@/types";

const WS_BASE_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000";

class WebSocketClient {
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private heartbeatTimeoutTimer: ReturnType<typeof setTimeout> | null = null;

  private readonly RECONNECT_BASE_DELAY = 1000;
  private readonly RECONNECT_MAX_DELAY = 30000;
  private readonly HEARTBEAT_INTERVAL = 30000;
  private readonly HEARTBEAT_TIMEOUT = 10000;
  private readonly MAX_RECONNECT_ATTEMPTS = 10;

  connect(): void {
    const token = useAuthStore.getState().getAccessToken();
    const tenant = useAuthStore.getState().tenant;

    if (!token || !tenant) {
      console.warn("[WS] Cannot connect: missing auth token or tenant");
      return;
    }

    this.disconnect();
    useWebSocketStore.getState().setStatus("connecting");

    const url = new URL(`${WS_BASE_URL}/ws/v1`);
    url.searchParams.set("token", token);
    url.searchParams.set("tenant_id", tenant.id);

    try {
      this.ws = new WebSocket(url.toString());

      this.ws.onopen = () => {
        console.log("[WS] Connected");
        useWebSocketStore.getState().setStatus("connected");
        useWebSocketStore.getState().resetReconnectAttempt();
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          this.handleMessage(message);
        } catch (err) {
          console.error("[WS] Failed to parse message:", err);
        }
      };

      this.ws.onclose = (event) => {
        console.log(`[WS] Closed: code=${event.code}, reason=${event.reason}`);
        this.stopHeartbeat();
        this.attemptReconnect();
      };

      this.ws.onerror = (error) => {
        console.error("[WS] Error:", error);
        useWebSocketStore.getState().setStatus("error");
      };
    } catch (err) {
      console.error("[WS] Failed to create connection:", err);
      useWebSocketStore.getState().setStatus("error");
      this.attemptReconnect();
    }
  }

  disconnect(): void {
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
    useWebSocketStore.getState().setStatus("disconnected");
  }

  private attemptReconnect(): void {
    const state = useWebSocketStore.getState();
    const attempt = state.reconnectAttempt;

    if (attempt >= this.MAX_RECONNECT_ATTEMPTS) {
      console.error("[WS] Max reconnect attempts reached");
      state.setStatus("disconnected");
      return;
    }

    state.setStatus("reconnecting");
    state.incrementReconnectAttempt();

    const delay = Math.min(
      this.RECONNECT_BASE_DELAY * 2 ** attempt,
      this.RECONNECT_MAX_DELAY
    );

    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${attempt + 1})`);

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, delay);
  }

  private startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: "ping", payload: {}, timestamp: new Date().toISOString(), tenantId: "" });
      this.heartbeatTimeoutTimer = setTimeout(() => {
        console.warn("[WS] Heartbeat timeout - no pong received");
        this.ws?.close();
      }, this.HEARTBEAT_TIMEOUT);
    }, this.HEARTBEAT_INTERVAL);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }
  }

  private send(message: WebSocketMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  listenToCall(callId: string): void {
    const tenant = useAuthStore.getState().tenant;
    this.send({
      type: "call_listen",
      payload: { callId },
      timestamp: new Date().toISOString(),
      tenantId: tenant?.id ?? "",
    });
  }

  takeOverCall(callId: string): void {
    const tenant = useAuthStore.getState().tenant;
    this.send({
      type: "call_takeover",
      payload: { callId },
      timestamp: new Date().toISOString(),
      tenantId: tenant?.id ?? "",
    });
  }

  private handleMessage(message: WebSocketMessage): void {
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer);
      this.heartbeatTimeoutTimer = null;
    }

    switch (message.type) {
      case "pong":
        break;

      case "call_started": {
        const call = message.payload as ActiveCall;
        useCallStore.getState().addActiveCall(call);
        break;
      }

      case "call_updated": {
        const { callId, updates } = message.payload as {
          callId: string;
          updates: Partial<ActiveCall>;
        };
        useCallStore.getState().updateActiveCall(callId, updates);
        break;
      }

      case "call_ended": {
        const callId = (message.payload as { callId: string }).callId;
        useCallStore.getState().removeActiveCall(callId);
        import("@/lib/query-client").then(({ queryClient }) => {
          queryClient.invalidateQueries({ queryKey: ["calls"] });
        });
        break;
      }

      case "transcript_updated": {
        const { callId, segment } = message.payload as {
          callId: string;
          segment: TranscriptSegment;
        };
        useCallStore.getState().appendTranscriptSegment(callId, segment);
        break;
      }

      case "message_received":
      case "notification_created": {
        const notification = message.payload as Notification;
        useNotificationStore.getState().addNotification(notification);
        break;
      }

      case "auth_success": {
        const { channel } = message.payload as { channel: string };
        useWebSocketStore.getState().addSubscribedChannel(channel);
        break;
      }

      case "usage_updated": {
        import("@/lib/query-client").then(({ queryClient }) => {
          queryClient.invalidateQueries({ queryKey: ["billing", "usage"] });
        });
        break;
      }

      default:
        console.log("[WS] Unhandled message type:", message.type);
    }
  }
}

export const wsClient = new WebSocketClient();
