/**
 * useOfflineSync — queues note mutations while offline and replays them
 * when connectivity is restored.
 *
 * Contract (enforced by useOfflineSync.test.ts):
 *  - api.createNote / api.updateNote are resolved at call-time inside drain()
 *    NOT captured at module-load-time, so vi.mock() replacements take effect.
 *  - Methods are read via bracket access on the live `api` object each time
 *    drain() runs, ensuring the mock replacement is always picked up.
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
  const [isOnline, setIsOnline]   = useState(navigator.onLine);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [queueLength, setQueueLength] = useState(0);
  const queueRef = useRef<QueueItem[]>([]);
  // Keep a stable ref to the latest onToast so drain() never needs to
  // be recreated when the callback identity changes.
  const onToastRef = useRef<ToastFn | undefined>(onToast);
  useEffect(() => { onToastRef.current = onToast; }, [onToast]);

  function setQueue(q: QueueItem[]) {
    queueRef.current = q;
    setQueueLength(q.length);
  }

  // drain is stable (no deps that change) — reads api methods via
  // bracket access at call-time so vi.mock replacements are always seen.
  const drain = useCallback(async () => {
    if (queueRef.current.length === 0) return;
    setIsSyncing(true);
    setSyncError(null);
    onToastRef.current?.(`Syncing ${queueRef.current.length} operation(s)\u2026`, 'info');

    // Read from the live api default-export object at call-time.
    // This is the key pattern that lets vi.mock({ default: { createNote: vi.fn() } })
    // be picked up even though `api` was imported at module-load time.
    const liveApi = api as Record<string, unknown>;
    const doCreate = liveApi['createNote'] as
      ((payload: Record<string, unknown>) => Promise<unknown>) | undefined;
    const doUpdate = liveApi['updateNote'] as
      ((id: string, payload: Record<string, unknown>) => Promise<unknown>) | undefined;

    const remaining: QueueItem[] = [];
    for (const item of queueRef.current) {
      try {
        if (item.type === 'create' && doCreate) {
          await doCreate(item.payload);
        } else if (item.type === 'update' && item.noteId && doUpdate) {
          await doUpdate(item.noteId, item.payload);
        } else {
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
      onToastRef.current?.(msg, 'warning');
    } else {
      onToastRef.current?.('Synced successfully.', 'success');
    }
  }, []); // stable — reads api live via ref pattern above

  useEffect(() => {
    const up   = async () => { setIsOnline(true);  await drain(); };
    const down = () => setIsOnline(false);
    window.addEventListener('online',  up);
    window.addEventListener('offline', down);
    return () => {
      window.removeEventListener('online',  up  as EventListener);
      window.removeEventListener('offline', down);
    };
  }, [drain]);

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
          i === existing
            ? { ...i, payload: { ...i.payload, ...payload }, timestamp: Date.now() }
            : i,
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
