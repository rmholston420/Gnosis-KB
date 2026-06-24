/**
 * useWebSocket / useVaultWebSocket
 * ================================
 * Manages a WebSocket connection to the backend.
 * Returns { lastMessage, send, readyState } so consumers can react to events.
 *
 * Used by VaultSyncWatcher to invalidate TanStack Query caches on live events.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

export type WsMessage = { type: string; data?: unknown };

export type ReadyState = 0 | 1 | 2 | 3;

const WS_BASE =
  (typeof import.meta !== 'undefined'
    ? (import.meta as unknown as { env?: Record<string, string> }).env?.VITE_WS_URL
    : undefined) ??
  `${typeof window !== 'undefined' && window.location.origin.replace(/^http/, 'ws')}/ws`;

function useWebSocket(url: string) {
  const wsRef                 = useRef<WebSocket | null>(null);
  const [lastMessage, setLastMessage] = useState<WsMessage | null>(null);
  const [readyState,  setReadyState]  = useState<ReadyState>(3); // CLOSED

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState < 2) return; // already open/connecting

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen    = () => setReadyState(1);
    ws.onclose   = () => {
      setReadyState(3);
      // Auto-reconnect after 3 s
      setTimeout(connect, 3000);
    };
    ws.onerror   = () => ws.close();
    ws.onmessage = (evt) => {
      try {
        const parsed = JSON.parse(evt.data as string) as WsMessage;
        setLastMessage(parsed);
      } catch {
        // ignore non-JSON frames
      }
    };
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === 1) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { lastMessage, send, readyState };
}

/**
 * Hook for the vault-sync event stream.
 * Returns { lastMessage, send, readyState } — consumed by VaultSyncWatcher.
 */
export function useVaultWebSocket() {
  return useWebSocket(`${WS_BASE}/vault`);
}

export default useWebSocket;
