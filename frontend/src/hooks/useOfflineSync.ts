/**
 * useOfflineSync
 * ==============
 * Manages an in-memory queue of note creates/updates that were attempted
 * while the browser was offline.  On reconnect the queue is drained
 * sequentially via the real API, with real toast feedback per item.
 *
 * Usage
 * -----
 *   const { queueCreate, queueUpdate, queueLength, draining } = useOfflineSync();
 *
 *   if (!navigator.onLine) {
 *     queueCreate(noteData);
 *   } else {
 *     await api.createNote(noteData);
 *   }
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../services/api';
import { toast } from './useToast';

interface QueueItem {
  id: string;
  type: 'create' | 'update';
  noteId?: string;
  payload: unknown;
}

function uuid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function useOfflineSync() {
  const queueRef = useRef<QueueItem[]>([]);
  const [queueLength, setQueueLength] = useState(0);
  const [draining, setDraining] = useState(false);
  const drainingRef = useRef(false);

  function syncQueueLength() {
    setQueueLength(queueRef.current.length);
  }

  const queueCreate = useCallback((payload: unknown) => {
    queueRef.current.push({ id: uuid(), type: 'create', payload });
    syncQueueLength();
  }, []);

  const queueUpdate = useCallback((noteId: string, payload: unknown) => {
    const existing = queueRef.current.findIndex(
      (item) => item.type === 'update' && item.noteId === noteId
    );
    if (existing >= 0) {
      queueRef.current[existing].payload = payload;
    } else {
      queueRef.current.push({ id: uuid(), type: 'update', noteId, payload });
    }
    syncQueueLength();
  }, []);

  const drainQueue = useCallback(async () => {
    if (drainingRef.current || queueRef.current.length === 0) return;
    drainingRef.current = true;
    setDraining(true);

    const total = queueRef.current.length;
    toast.info(`Syncing ${total} offline change${total > 1 ? 's' : ''}…`);

    let succeeded = 0;
    let failed = 0;

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
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        toast.error(`Sync failed for "${(item.payload as { title?: string })?.title ?? item.id}": ${msg}`);
        queueRef.current.shift();
        queueRef.current.push({ ...item, id: uuid() });
        failed++;
        if (failed >= total) break;
      }
    }

    syncQueueLength();
    drainingRef.current = false;
    setDraining(false);

    if (succeeded > 0) {
      toast.success(`✓ Synced ${succeeded} offline note${succeeded > 1 ? 's' : ''}`);
    }
    if (failed > 0) {
      toast.error(`${failed} item${failed > 1 ? 's' : ''} could not be synced and remain queued.`, 8000);
    }
  }, []);

  useEffect(() => {
    const handleOnline = () => { void drainQueue(); };
    window.addEventListener('online', handleOnline);
    return () => window.removeEventListener('online', handleOnline);
  }, [drainQueue]);

  return { queueCreate, queueUpdate, queueLength, draining, drainQueue };
}

export default useOfflineSync;
