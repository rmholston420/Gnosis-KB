/**
 * VaultSyncWatcher
 * ================
 * Invisible component mounted at the App root that subscribes to live
 * vault-sync WebSocket events and invalidates the relevant TanStack Query
 * caches so every view reflects the updated state without a page reload.
 *
 * Events handled:
 *   sync_started   → show a subtle toast / status indicator (via aiStore)
 *   sync_progress  → update progress counter in aiStore
 *   sync_complete  → invalidate notes + graph + search queries
 *   sync_error     → set error flag in aiStore
 *   note_created   → invalidate notes list
 *   note_updated   → invalidate the specific note + notes list
 *   note_deleted   → invalidate notes list + graph
 */
import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useVaultWebSocket } from '../hooks/useWebSocket';
import { useAiStore } from '../store/aiStore';

export function VaultSyncWatcher() {
  const qc = useQueryClient();
  const { setVaultSyncStatus, setVaultSyncProgress } = useAiStore();

  const { lastMessage } = useVaultWebSocket();

  useEffect(() => {
    if (!lastMessage) return;

    const { type, data } = lastMessage as { type: string; data?: unknown };

    switch (type) {
      case 'sync_started':
        setVaultSyncStatus('syncing');
        break;

      case 'sync_progress':
        if (typeof (data as { progress?: number })?.progress === 'number') {
          setVaultSyncProgress((data as { progress: number }).progress);
        }
        break;

      case 'sync_complete':
        setVaultSyncStatus('idle');
        qc.invalidateQueries({ queryKey: ['notes'] });
        qc.invalidateQueries({ queryKey: ['graph'] });
        qc.invalidateQueries({ queryKey: ['search'] });
        break;

      case 'sync_error':
        setVaultSyncStatus('error');
        break;

      case 'note_created':
        qc.invalidateQueries({ queryKey: ['notes'] });
        break;

      case 'note_updated': {
        const noteId = (data as { note_id?: string })?.note_id;
        if (noteId) qc.invalidateQueries({ queryKey: ['note', noteId] });
        qc.invalidateQueries({ queryKey: ['notes'] });
        break;
      }

      case 'note_deleted':
        qc.invalidateQueries({ queryKey: ['notes'] });
        qc.invalidateQueries({ queryKey: ['graph'] });
        break;

      default:
        break;
    }
  }, [lastMessage]);

  return null;
}
