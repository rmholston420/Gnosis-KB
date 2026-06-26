/**
 * useWebSocket — real-time vault watcher updates via WebSocket.
 *
 * Connects to the FastAPI /api/v1/ws/vault endpoint and fires callbacks
 * when notes are created, updated, or deleted by the vault sync service.
 *
 * Auth note
 * ---------
 * WebSocket handshake requests cannot carry an Authorization header (the
 * browser WS API doesn't support it). The token is sent as a query param.
 * Token storage key is 'gnosis_token' in localStorage — same as client.ts.
 *
 * When AUTH_REQUIRED=false (local dev default) the backend accepts
 * connections without a token, so omitting the param is correct and clean.
 *
 * FIX: lastMessage is now useState (was useRef.current).
 * useRef mutations do not schedule re-renders, so every consumer of
 * lastMessage always received the initial `undefined` regardless of how
 * many vault events arrived. Switching to useState ensures consumers
 * re-render when a new event is dispatched.
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { NOTES_KEY } from './useNotes';

export type VaultEvent =
  | { type: 'note_created'; note_id: string; title: string }
  | { type: 'note_updated'; note_id: string }
  | { type: 'note_deleted'; note_id: string }
  | { type: 'sync_complete'; synced: number }
  | { type: 'ping' };

const WS_BASE = (() => {
  const base = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8010';
  return base.replace(/^https/, 'wss').replace(/^http/, 'ws');
})();

/** Build the WS URL. Omit ?token entirely when no token is present. */
function _wsUrl(): string {
  const token =
    typeof localStorage !== 'undefined'
      ? localStorage.getItem('gnosis_token')
      : null;
  const base = `${WS_BASE}/api/v1/ws/vault`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

/**
 * Subscribes to the vault watcher WebSocket and automatically invalidates
 * TanStack Query caches when vault events arrive.
 *
 * @param onEvent — optional callback for each raw event
 * @returns { lastMessage } — last raw VaultEvent received, or undefined
 */
export function useVaultWebSocket(
  onEvent?: (evt: VaultEvent) => void,
): { lastMessage: VaultEvent | undefined } {
  const qc = useQueryClient();
  const wsRef = useRef<WebSocket | null>(null);
  const cbRef = useRef(onEvent);
  const retryCountRef = useRef(0);
  // FIX: was useRef — ref mutations don't trigger re-renders so lastMessage
  // was always undefined from the consumer's perspective.
  const [lastMessage, setLastMessage] = useState<VaultEvent | undefined>(undefined);
  cbRef.current = onEvent;

  const connect = useCallback(() => {
    // Avoid double-connect from React StrictMode double-invoke.
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.CONNECTING ||
        wsRef.current.readyState === WebSocket.OPEN)
    ) {
      return;
    }

    let ws: WebSocket;
    try {
      ws = new WebSocket(_wsUrl());
    } catch (err) {
      console.warn('[WS] Failed to open WebSocket:', err);
      return;
    }
    wsRef.current = ws;

    ws.onopen = () => {
      retryCountRef.current = 0;
    };

    ws.onmessage = (ev) => {
      let evt: VaultEvent | null = null;
      try {
        evt = JSON.parse(ev.data) as VaultEvent;
      } catch {
        return;
      }

      // Ignore server keep-alive pings — no cache invalidation needed.
      if (evt.type === 'ping') return;

      // FIX: setState instead of mutating ref so consumers re-render
      setLastMessage(evt);
      cbRef.current?.(evt);

      switch (evt.type) {
        case 'note_created':
        case 'note_updated':
          void qc.invalidateQueries({ queryKey: [NOTES_KEY, evt.note_id] });
          void qc.invalidateQueries({ queryKey: [NOTES_KEY] });
          break;
        case 'note_deleted':
          void qc.invalidateQueries({ queryKey: [NOTES_KEY] });
          break;
        case 'sync_complete':
          void qc.invalidateQueries({ queryKey: [NOTES_KEY] });
          void qc.invalidateQueries({ queryKey: ['graph'] });
          break;
      }
    };

    ws.onerror = () => {
      // onclose fires immediately after onerror — let onclose handle retry.
    };

    ws.onclose = (ev) => {
      // 4001 = auth rejected by server — don't retry endlessly.
      if (ev.code === 4001) {
        console.warn('[WS] Vault WebSocket: auth rejected (4001). Will not retry.');
        return;
      }
      // Exponential backoff: 1s, 2s, 4s … capped at 30s.
      const delay = Math.min(1000 * 2 ** retryCountRef.current, 30_000);
      retryCountRef.current += 1;
      setTimeout(connect, delay);
    };
  }, [qc]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) {
        // Neutralise onclose so cleanup doesn't schedule a reconnect.
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { lastMessage };
}
