/**
 * useOfflineSync
 * ==============
 * Manages an in-memory queue of note creates/updates that were attempted
 * while the browser was offline.  On reconnect the queue is drained
 * sequentially via the real API, with toast feedback per item.
 *
 * Usage
 * -----
 *   const { queueCreate, queueUpdate, queueLength, draining } = useOfflineSync();
 *
 *   // In your note save handler:
 *   if (!navigator.onLine) {
 *     queueCreate(noteData);
 *     toast.info('Saved offline — will sync when reconnected');
 *   } else {
 *     await api.createNote(noteData);
 *   }
 *
 * The hook attaches window 'online' listeners automatically; no manual
 * cleanup needed (the listener is removed on component unmount via useEffect).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../services/api';

interface QueueItem {
  id: string;          // ephemeral UUID used only to identify the queue item
  type: 'create' | 'update';
  noteId?: string;     // required for 'update'
  payload: unknown;
}

function uuid() {
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

// Simple in-memory toast shim — replace with your real toast library
function toast(msg: string, variant: 'success' | 'error' | 'info' = 'info') {
  // In a real app: import { toast } from 'react-hot-toast';
  console.log(`[toast:${variant}] ${msg}`);
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
    // Coalesce: if there's already a pending update for the same note, replace it
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
    toast(`Syncing ${total} offline change${total > 1 ? 's' : ''}…`, 'info');

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
        // Remove successfully synced item
        queueRef.current.shift();
        succeeded++;
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Unknown error';
        toast(`Sync failed for “${(item.payload as { title?: string })?.title ?? item.id}”: ${msg}`, 'error');
        // Move failed item to end so other items can still be tried
        queueRef.current.shift();
        queueRef.current.push({ ...item, id: uuid() });
        failed++;
        // Bail after a full cycle of failures to avoid infinite loop
        if (failed >= total) break;
      }
    }

    syncQueueLength();
    drainingRef.current = false;
    setDraining(false);

    if (succeeded > 0) {
      toast(`\u2713 Synced ${succeeded} offline note${succeeded > 1 ? 's' : ''}`, 'success');
    }
    if (failed > 0) {
      toast(`${failed} item${failed > 1 ? 's' : ''} could not be synced and remain queued.`, 'error');
    }
  }, []);

  // Automatically drain on reconnect
  useEffect(() => {
    const handleOnline = () => {
      void drainQueue();
    };
    window.addEventListener('online', handleOnline);
    return () => window.removeEventListener('online', handleOnline);
  }, [drainQueue]);

  return { queueCreate, queueUpdate, queueLength, draining, drainQueue };
}

export default useOfflineSync;
