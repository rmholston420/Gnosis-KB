/**
 * OfflineBanner
 * =============
 * Sticky top banner that appears when the user is offline or there are
 * queued changes waiting to sync.
 *
 * Props:
 *   isOnline      — current online/offline state
 *   queuedCount   — number of changes waiting to sync
 *   onSyncClick   — called when the user clicks "Retry sync"
 */

import React from 'react';
import { Wifi, WifiOff, RefreshCw } from 'lucide-react';

interface OfflineBannerProps {
  isOnline: boolean;
  queuedCount: number;
  onSyncClick: () => void;
}

export function OfflineBanner({ isOnline, queuedCount, onSyncClick }: OfflineBannerProps) {
  // Show banner when:
  //  a) offline regardless of queue
  //  b) online but there are queued changes to flush
  const show = !isOnline || queuedCount > 0;
  if (!show) return null;

  const offline  = !isOnline;
  const hasQueue = queuedCount > 0;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 50,
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.5rem',
        padding: '0.375rem 1rem',
        fontSize: '0.8125rem',
        fontWeight: 500,
        backgroundColor: offline ? 'var(--color-warning-highlight)' : 'var(--color-primary-highlight)',
        color: offline ? 'var(--color-warning)' : 'var(--color-primary)',
        borderBottom: '1px solid',
        borderColor: offline ? 'var(--color-warning)' : 'var(--color-primary)',
      }}
    >
      {offline ? <WifiOff size={14} /> : <Wifi size={14} />}

      <span>
        {offline && hasQueue
          ? `Offline — ${queuedCount} change${queuedCount > 1 ? 's' : ''} queued`
          : offline
          ? 'You are offline — changes will sync when reconnected'
          : `${queuedCount} change${queuedCount > 1 ? 's' : ''} queued — tap to sync`}
      </span>

      {(hasQueue || offline) && (
        <button
          onClick={() => { onSyncClick(); }}
          disabled={offline}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.25rem',
            padding: '0.125rem 0.5rem',
            borderRadius: '0.25rem',
            border: '1px solid currentColor',
            background: 'none',
            color: 'inherit',
            cursor: offline ? 'not-allowed' : 'pointer',
            opacity: offline ? 0.5 : 1,
            fontSize: '0.75rem',
          }}
          aria-label="Retry sync"
        >
          <RefreshCw size={11} />
          {offline ? 'Offline' : 'Sync now'}
        </button>
      )}
    </div>
  );
}
