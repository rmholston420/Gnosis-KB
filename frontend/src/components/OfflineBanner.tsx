/**
 * OfflineBanner.tsx
 *
 * Amber sticky banner shown when the app is offline.
 * Displays the number of queued mutations and a manual sync button.
 *
 * Props:
 *   isOnline      — hides the banner when true
 *   queuedCount   — number shown in the badge (0 = hide badge)
 *   onSyncClick   — called when the user clicks "Retry sync"
 *
 * Animation:
 *   Slides down from above on mount, slides back up on unmount.
 *   Respects prefers-reduced-motion: falls back to instant show/hide.
 */

import React, { useEffect, useRef, useState } from 'react';

interface OfflineBannerProps {
  isOnline: boolean;
  queuedCount: number;
  onSyncClick: () => Promise<void>;
}

export const OfflineBanner: React.FC<OfflineBannerProps> = ({
  isOnline,
  queuedCount,
  onSyncClick,
}) => {
  const [visible, setVisible]     = useState(!isOnline);
  const [syncing, setSyncing]     = useState(false);
  const [mounted, setMounted]     = useState(!isOnline);
  const prefersReduced = useRef(
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );

  useEffect(() => {
    if (!isOnline) {
      setMounted(true);
      // Small rAF delay so the slide-in transition fires after mount
      requestAnimationFrame(() => setVisible(true));
    } else {
      setVisible(false);
      // Unmount after the slide-out transition completes
      const timer = setTimeout(() => setMounted(false), 300);
      return () => clearTimeout(timer);
    }
  }, [isOnline]);

  if (!mounted) return null;

  const handleSync = async () => {
    setSyncing(true);
    try {
      await onSyncClick();
    } finally {
      setSyncing(false);
    }
  };

  const transitionStyle: React.CSSProperties = prefersReduced.current
    ? {}
    : {
        transition: 'transform 300ms cubic-bezier(0.16, 1, 0.3, 1), opacity 300ms ease',
        transform: visible ? 'translateY(0)' : 'translateY(-110%)',
        opacity:   visible ? 1 : 0,
      };

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Offline status"
      style={{
        position:        'sticky',
        top:             0,
        zIndex:          9999,
        display:         'flex',
        alignItems:      'center',
        gap:             '0.5rem',
        padding:         '0.5rem 1rem',
        backgroundColor: '#92400e', // amber-800
        color:           '#fef3c7', // amber-100
        fontSize:        '0.875rem',
        fontWeight:      500,
        boxShadow:       '0 2px 8px rgba(0,0,0,0.3)',
        ...transitionStyle,
      }}
    >
      {/* Offline icon */}
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <line x1="1" y1="1" x2="23" y2="23" />
        <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
        <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
        <path d="M10.71 5.05A16 16 0 0 1 22.56 9" />
        <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
        <path d="M8.53 16.11a6 6 0 0 1 6.95 0" />
        <line x1="12" y1="20" x2="12.01" y2="20" />
      </svg>

      <span style={{ flex: 1 }}>
        You are offline.
        {queuedCount > 0 && (
          <>
            {' '}
            <strong
              style={{
                display:         'inline-flex',
                alignItems:      'center',
                justifyContent:  'center',
                minWidth:        '1.25rem',
                height:          '1.25rem',
                padding:         '0 0.25rem',
                borderRadius:    '9999px',
                backgroundColor: '#d97706', // amber-600
                color:           '#fff',
                fontSize:        '0.75rem',
                fontWeight:      700,
              }}
              aria-label={`${queuedCount} change${queuedCount === 1 ? '' : 's'} queued`}
            >
              {queuedCount}
            </strong>
            {' '}
            {queuedCount === 1 ? 'change queued' : 'changes queued'} — will sync
            when reconnected.
          </>
        )}
        {queuedCount === 0 && ' Changes will sync when reconnected.'}
      </span>

      <button
        onClick={handleSync}
        disabled={syncing}
        aria-label="Retry sync now"
        style={{
          padding:         '0.25rem 0.75rem',
          borderRadius:    '0.375rem',
          border:          '1px solid rgba(254,243,199,0.4)',
          backgroundColor: 'transparent',
          color:           '#fef3c7',
          cursor:          syncing ? 'not-allowed' : 'pointer',
          opacity:         syncing ? 0.6 : 1,
          fontSize:        '0.8125rem',
          fontWeight:      500,
          transition:      'background 180ms ease, opacity 180ms ease',
          whiteSpace:      'nowrap',
        }}
        onMouseEnter={(e) =>
          ((e.target as HTMLButtonElement).style.backgroundColor = 'rgba(254,243,199,0.1)')
        }
        onMouseLeave={(e) =>
          ((e.target as HTMLButtonElement).style.backgroundColor = 'transparent')
        }
      >
        {syncing ? 'Syncing…' : 'Retry sync'}
      </button>
    </div>
  );
};

export default OfflineBanner;
