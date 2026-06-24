/**
 * useWebSocket — real-time vault watcher updates via WebSocket.
 * Connects to the FastAPI backend WS endpoint and fires callbacks
 * when notes are created, updated, or deleted by the vault sync service.
 */
import { useEffect, useRef, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { NOTES_KEY } from './useNotes';

export type VaultEvent =
  | { type: 'note_created'; note_id: string; title: string }
  | { type: 'note_updated'; note_id: string }
  | { type: 'note_deleted'; note_id: string }
  | { type: 'sync_complete'; synced: number };

const WS_BASE = (() => {
  const base = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8010';
  return base.replace(/^https?/, base.startsWith('https') ? 'wss' : 'ws');
})();

/**
 * Subscribes to the vault watcher WebSocket and automatically invalidates
 * TanStack Query caches when vault events arrive.
 *
 * @param onEvent — optional callback for each raw event
 */
export function useVaultWebSocket(onEvent?: (evt: VaultEvent) => void) {
  const qc     = useQueryClient();
  const wsRef  = useRef<WebSocket | null>(null);
  const cbRef  = useRef(onEvent);
  cbRef.current = onEvent;

  const connect = useCallback(() => {
    const token = localStorage.getItem('gnosis_token');
    const url   = `${WS_BASE}/api/v1/ws/vault?token=${token ?? ''}`;
    const ws    = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (ev) => {
      let evt: VaultEvent | null = null;
      try { evt = JSON.parse(ev.data) as VaultEvent; } catch { return; }

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

    ws.onclose = () => {
      const delay = Math.min(1000 * 2 ** (wsRef.current?.readyState ?? 0), 30_000);
      setTimeout(connect, delay);
    };
  }, [qc]);

  useEffect(() => {
    connect();
    return () => { wsRef.current?.close(); };
  }, [connect]);
}
