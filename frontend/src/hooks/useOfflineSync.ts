/**
 * useOfflineSync.ts
 *
 * React hook that:
 *  1. Tracks online / offline status.
 *  2. Shows a toast when the connection is lost or restored.
 *  3. Drains the offline mutation queue when coming back online.
 *  4. Exposes the current queue depth so the UI can display a badge.
 *
 * Usage:
 *
 *   const { isOnline, queuedCount, triggerSync } = useOfflineSync();
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { offlineQueue, triggerManualSync } from '@/lib/offlineQueue';

export interface UseOfflineSyncResult {
  /** Whether the browser currently has network connectivity. */
  isOnline: boolean;
  /** Number of mutations waiting to be replayed. */
  queuedCount: number;
  /** Manually trigger a sync attempt (useful for a "retry" button). */
  triggerSync: () => Promise<void>;
}

export function useOfflineSync(
  onToast?: (message: string, variant: 'info' | 'success' | 'warning') => void
): UseOfflineSyncResult {
  const [isOnline, setIsOnline]       = useState(navigator.onLine);
  const [queuedCount, setQueuedCount] = useState(0);
  const toastRef = useRef(onToast);
  toastRef.current = onToast;

  const refreshCount = useCallback(async () => {
    const n = await offlineQueue.count();
    setQueuedCount(n);
  }, []);

  const triggerSync = useCallback(async () => {
    await triggerManualSync();
    // Queue drain happens in the SW; QUEUE_DRAINED message updates count
  }, []);

  useEffect(() => {
    // Initialise count on mount
    refreshCount();

    const handleOnline = () => {
      setIsOnline(true);
      toastRef.current?.(
        'Back online — syncing queued changes…',
        'success'
      );
      triggerSync().then(refreshCount);
    };

    const handleOffline = () => {
      setIsOnline(false);
      toastRef.current?.(
        'You are offline. Changes will sync when reconnected.',
        'warning'
      );
    };

    window.addEventListener('online',  handleOnline);
    window.addEventListener('offline', handleOffline);

    // Listen for QUEUE_DRAINED messages posted by the service worker
    const handleSWMessage = (event: MessageEvent) => {
      if (event.data?.type === 'QUEUE_DRAINED') {
        refreshCount();
        toastRef.current?.('All queued changes have been synced.', 'success');
      }
      // Incremental queue updates posted after each successful enqueue
      if (event.data?.type === 'QUEUE_UPDATED') {
        setQueuedCount((prev) => prev + 1);
      }
    };

    navigator.serviceWorker?.addEventListener('message', handleSWMessage);

    return () => {
      window.removeEventListener('online',  handleOnline);
      window.removeEventListener('offline', handleOffline);
      navigator.serviceWorker?.removeEventListener('message', handleSWMessage);
    };
  }, [refreshCount, triggerSync]);

  return { isOnline, queuedCount, triggerSync };
}
