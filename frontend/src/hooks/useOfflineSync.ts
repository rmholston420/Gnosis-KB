/**
 * useOfflineSync
 * ==============
 * Manages an in-memory queue of note creates/updates attempted while offline.
 * On reconnect the queue is drained sequentially via the real API.
 *
 * Signature (unchanged from pre-Slice-8 contract used by App.tsx):
 *   const { isOnline, queuedCount, triggerSync } = useOfflineSync(onToast);
 *
 * onToast is the react-hot-toast callback injected by App.tsx so toasts use
 * the same Toaster instance already mounted there.  Internally we also
 * call the same callback for granular per-item feedback.
 *
 * Additional exports:
 *   queueCreate(payload)  — queue a create-note payload
 *   queueUpdate(id, payload) — queue/merge an update-note payload
 *   draining              — true while drain is in progress
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../services/api';

type ToastVariant = 'info' | 'success' | 'warning';
type ToastCallback = (message: string, variant: ToastVariant) => void;

interface QueueItem {
  id: string;
  type: 'create' | 'update';
  noteId?: string;
  payload: unknown;
}

function uuid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function useOfflineSync(onToast?: ToastCallback) {
  const [isOnline, setIsOnline]   = useState(navigator.onLine);
  const [queuedCount, setQueuedCount] = useState(0);
  const [draining, setDraining]   = useState(false);

  const queueRef    = useRef<QueueItem[]>([]);
  const drainingRef = useRef(false);

  function syncCount() { setQueuedCount(queueRef.current.length); }

  const queueCreate = useCallback((payload: unknown) => {
    queueRef.current.push({ id: uuid(), type: 'create', payload });
    syncCount();
  }, []);

  const queueUpdate = useCallback((noteId: string, payload: unknown) => {
    const i = queueRef.current.findIndex(
      (item) => item.type === 'update' && item.noteId === noteId,
    );
    if (i >= 0) {
      queueRef.current[i].payload = payload;
    } else {
      queueRef.current.push({ id: uuid(), type: 'update', noteId, payload });
    }
    syncCount();
  }, []);

  const drainQueue = useCallback(async () => {
    if (drainingRef.current || queueRef.current.length === 0) return;
    drainingRef.current = true;
    setDraining(true);

    const total = queueRef.current.length;
    onToast?.(`Syncing ${total} offline change${total > 1 ? 's' : ''}…`, 'info');

    let succeeded = 0;
    let failed    = 0;

    while (queueRef.current.length > 0) {
      const item = queueRef.current[0];
      try {
        if (item.type === 'create') {
          await api.createNote(item.payload);
        } else if (item.type === 'update' && item.noteId) {
          await api.updateNote(item.noteId, item.payload);
        }
        queueRef.current.shift();
        succeeded++;
      } catch {
        const title = (item.payload as { title?: string })?.title ?? item.id;
        onToast?.(`Sync failed for "${title}" — will retry on next reconnect.`, 'warning');
        // Move failing item to tail; break if all items are failing
        queueRef.current.shift();
        queueRef.current.push({ ...item, id: uuid() });
        failed++;
        if (failed >= total) break;
      }
    }

    syncCount();
    drainingRef.current = false;
    setDraining(false);

    if (succeeded > 0) {
      onToast?.(`✓ Synced ${succeeded} offline note${succeeded > 1 ? 's' : ''}`, 'success');
    }
  }, [onToast]);

  const triggerSync = useCallback(() => { void drainQueue(); }, [drainQueue]);

  useEffect(() => {
    function handleOnline() {
      setIsOnline(true);
      void drainQueue();
    }
    function handleOffline() { setIsOnline(false); }

    window.addEventListener('online',  handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online',  handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [drainQueue]);

  return { isOnline, queuedCount, triggerSync, queueCreate, queueUpdate, draining };
}

export default useOfflineSync;
