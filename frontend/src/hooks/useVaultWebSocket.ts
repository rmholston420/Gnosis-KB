/**
 * useVaultWebSocket — WebSocket hook for real-time vault sync notifications.
 *
 * Returns the last message received from the vault sync WebSocket, plus
 * a connection status flag. Components can watch `lastMessage` to react
 * to sync events without polling.
 *
 * The hook is intentionally lightweight: it opens a single WebSocket
 * connection per component mount, closes it on unmount, and exposes only
 * the data consumers actually need.
 */
import { useEffect, useRef, useState } from 'react';

export interface VaultWebSocketMessage {
  type:    string;
  payload: unknown;
}

export interface UseVaultWebSocketReturn {
  lastMessage: VaultWebSocketMessage | null;
  connected:   boolean;
}

export function useVaultWebSocket(): UseVaultWebSocketReturn {
  const [lastMessage, setLastMessage] = useState<VaultWebSocketMessage | null>(null);
  const [connected, setConnected]     = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const BASE_WS = (import.meta as any).env?.VITE_WS_URL
      ?? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}`;
    const url = `${BASE_WS}/ws/vault-sync`;

    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch {
      // In test environments WebSocket may not be available; fail silently.
      return;
    }

    wsRef.current = ws;

    ws.onopen  = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (evt: MessageEvent) => {
      try {
        const data = JSON.parse(evt.data as string) as VaultWebSocketMessage;
        setLastMessage(data);
      } catch {
        setLastMessage({ type: 'raw', payload: evt.data });
      }
    };

    return () => { ws.close(); };
  }, []);

  return { lastMessage, connected };
}
