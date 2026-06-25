/**
 * useOfflineSync — queues note mutations while offline and replays them
 * when connectivity is restored.
 *
 * Contract (enforced by useOfflineSync.test.ts):
 *  - api.createNote / api.updateNote are resolved at call-time inside drain()
 *    NOT captured at module-load-time, so vi.mock() replacements take effect.
 */
import { useEffect, useRef, useState, useCallback } from 'react';
import api from '../services/api';

export type OperationType = 'create' | 'update';

export interface QueueItem {
  id: string;
  type: OperationType;
  noteId?: string;
  payload: Record<string, unknown>;
  timestamp: number;
}

type ToastFn = (message: string, level: 'info' | 'success' | 'warning' | 'error') => void;

export function useOfflineSync(onToast?: ToastFn) {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [queueLength, setQueueLength] = useState(0);
  const queueRef = useRef<QueueItem[]>([]);

  function setQueue(q: QueueItem[]) {
    queueRef.current = q;
    setQueueLength(q.length);
  }

  const drain = useCallback(async () => {
    if (queueRef.current.length === 0) return;
    setIsSyncing(true);
    setSyncError(null);
    onToast?.(`Syncing ${queueRef.current.length} operation(s)\u2026`, 'info');

    // Resolve api methods at call-time so vi.mock replacements are picked up
    const doCreate = (api as Record<string, unknown>).createNote as
      ((payload: Record<string, unknown>) => Promise<unknown>) | undefined;
    const doUpdate = (api as Record<string, unknown>).updateNote as
      ((id: string, payload: Record<string, unknown>) => Promise<unknown>) | undefined;

    const remaining: QueueItem[] = [];
    for (const item of queueRef.current) {
      try {
        if (item.type === 'create' && doCreate) {
          await doCreate(item.payload);
        } else if (item.type === 'update' && item.noteId && doUpdate) {
          await doUpdate(item.noteId, item.payload);
        } else {
          // No handler available — keep in queue
          remaining.push(item);
        }
      } catch {
        remaining.push(item);
      }
    }

    setQueue(remaining);
    setIsSyncing(false);

    if (remaining.length > 0) {
      const msg = `Sync failed for ${remaining.length} operation(s).`;
      setSyncError(msg);
      onToast?.(msg, 'warning');
    } else {
      onToast?.('Synced successfully.', 'success');
    }
  }, [onToast]);

  useEffect(() => {
    const up   = () => setIsOnline(true);
    const down = () => setIsOnline(false);
    window.addEventListener('online',  up);
    window.addEventListener('offline', down);
    return () => {
      window.removeEventListener('online',  up);
      window.removeEventListener('offline', down);
    };
  }, []);

  useEffect(() => {
    if (isOnline) void drain();
  }, [isOnline, drain]);

  function enqueue(type: OperationType, payload: Record<string, unknown>, noteId?: string) {
    const item: QueueItem = {
      id: crypto.randomUUID(),
      type,
      noteId,
      payload,
      timestamp: Date.now(),
    };
    setQueue([...queueRef.current, item]);
  }

  function queueCreate(payload: Record<string, unknown>) {
    enqueue('create', payload);
  }

  function queueUpdate(noteId: string, payload: Record<string, unknown>) {
    const existing = queueRef.current.find((i) => i.type === 'update' && i.noteId === noteId);
    if (existing) {
      setQueue(
        queueRef.current.map((i) =>
          i === existing ? { ...i, payload: { ...i.payload, ...payload }, timestamp: Date.now() } : i,
        ),
      );
    } else {
      enqueue('update', payload, noteId);
    }
  }

  async function triggerSync() {
    await drain();
  }

  return {
    isOnline,
    isSyncing,
    syncError,
    enqueue,
    queueCreate,
    queueUpdate,
    triggerSync,
    queueLength,
    queuedCount: queueLength,
  };
}
