/**
 * useOfflineSync — queues note mutations while offline and replays them
 * when connectivity is restored.
 */
import { useEffect, useRef, useState } from 'react';
import { createNote, updateNote } from '../services/api';

type OperationType = 'create' | 'update';

interface QueueItem {
  id:        string;
  type:      OperationType;
  noteId?:   string;
  payload:   Record<string, unknown>;
  timestamp: number;
}

const QUEUE_KEY = 'gnosis_offline_queue';

function loadQueue(): QueueItem[] {
  try {
    const raw = localStorage.getItem(QUEUE_KEY);
    return raw ? (JSON.parse(raw) as QueueItem[]) : [];
  } catch {
    return [];
  }
}

function saveQueue(q: QueueItem[]): void {
  try { localStorage.setItem(QUEUE_KEY, JSON.stringify(q)); } catch { /* ignore */ }
}

export function useOfflineSync() {
  const [isOnline, setIsOnline]   = useState(navigator.onLine);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const queueRef = useRef<QueueItem[]>(loadQueue());

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

  // Replay queue when coming back online
  useEffect(() => {
    if (!isOnline || queueRef.current.length === 0) return;
    (async () => {
      setIsSyncing(true);
      setSyncError(null);
      const remaining: QueueItem[] = [];
      for (const item of queueRef.current) {
        try {
          if (item.type === 'create') {
            await createNote(item.payload);
          } else if (item.type === 'update' && item.noteId) {
            await updateNote(item.noteId, item.payload);
          }
        } catch {
          remaining.push(item);
        }
      }
      queueRef.current = remaining;
      saveQueue(remaining);
      setIsSyncing(false);
      if (remaining.length > 0) {
        setSyncError(`${remaining.length} operations failed to sync.`);
      }
    })();
  }, [isOnline]);

  function enqueue(type: OperationType, payload: Record<string, unknown>, noteId?: string) {
    const item: QueueItem = {
      id:        crypto.randomUUID(),
      type,
      noteId,
      payload,
      timestamp: Date.now(),
    };
    queueRef.current = [...queueRef.current, item];
    saveQueue(queueRef.current);
  }

  return { isOnline, isSyncing, syncError, enqueue, queueLength: queueRef.current.length };
}
