/**
 * useWebSocket — real-time vault watcher updates via WebSocket.
 *
 * Connects to the FastAPI /api/v1/ws/vault endpoint and fires callbacks
 * when notes are created, updated, or deleted by the vault sync service.
 *
 * Auth note
 * ---------
 * WebSocket handshake requests cannot carry an Authorization header (the
 * browser WS API doesn't support it).  The token is sent as a query param
 * instead.  We read it from the apiClient axios instance's default headers
 * (set at login time) — NOT from localStorage, which is never written.
 *
 * When AUTH_REQUIRED=false (local dev, the default) the backend accepts
 * connections without a token by auto-resolving the first DB user, so the
 * empty-string fallback works fine.
 */
import { useEffect, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { NOTES_KEY } from './useNotes';
import { apiClient } from '../api/client';

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

/** Extract the Bearer token from the shared axios instance, if set. */
function _getToken(): string {
  const auth = apiClient.defaults.headers.common['Authorization'] as string | undefined;
  if (!auth) return '';
  // Header value is "Bearer <token>" — strip the prefix.
  return auth.startsWith('Bearer ') ? auth.slice(7) : auth;
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
  const lastMsgRef = useRef<VaultEvent | undefined>(undefined);
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

    const token = _getToken();
    const url = token
      ? `${WS_BASE}/api/v1/ws/vault?token=${encodeURIComponent(token)}`
      : `${WS_BASE}/api/v1/ws/vault`;

    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch (err) {
      // URL construction can fail if the base URL is malformed.
      console.warn('[WS] Failed to construct WebSocket URL:', err);
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

      lastMsgRef.current = evt;
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
      // 4001 = auth rejected by server — don't retry.
      if (ev.code === 4001) {
        console.warn('[WS] Vault WebSocket closed: auth rejected (4001). Will not retry.');
        return;
      }
      // Exponential backoff: 1s, 2s, 4s … max 30s
      const delay = Math.min(1000 * 2 ** retryCountRef.current, 30_000);
      retryCountRef.current += 1;
      setTimeout(connect, delay);
    };
  }, [qc]);

  useEffect(() => {
    connect();
    return () => {
      // Close without triggering reconnect on unmount.
      if (wsRef.current) {
        // Temporarily neutralise onclose so the cleanup doesn't schedule a reconnect.
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);

  return { lastMessage: lastMsgRef.current };
}
