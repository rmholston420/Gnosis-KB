import React, { useCallback } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster, toast } from 'react-hot-toast';

import { OfflineBanner }    from '@/components/OfflineBanner';
import { useOfflineSync }   from '@/hooks/useOfflineSync';
import { registerSW, skipWaiting } from '@/registerSW';

// Lazy-load all pages to keep the initial bundle small
const LoginPage        = React.lazy(() => import('@/pages/LoginPage'));
const NotesPage        = React.lazy(() => import('@/pages/NotesPage'));
const NoteEditorPage   = React.lazy(() => import('@/pages/NoteEditorPage'));
const GraphPage        = React.lazy(() => import('@/pages/GraphPage'));
const SearchPage       = React.lazy(() => import('@/pages/SearchPage'));
const AIPage           = React.lazy(() => import('@/pages/AIPage'));
const SettingsPage     = React.lazy(() => import('@/pages/SettingsPage'));
const QueryPage        = React.lazy(() => import('@/pages/QueryPage'));

// Register SW once at app startup (idempotent)
registerSW({
  onNeedRefresh: () => {
    toast(
      (t) => (
        <span>
          A new version of Gnosis is available.{' '}
          <button
            onClick={() => {
              skipWaiting();
              toast.dismiss(t.id);
            }}
            style={{ fontWeight: 600, textDecoration: 'underline', cursor: 'pointer' }}
          >
            Reload now
          </button>
        </span>
      ),
      { duration: Infinity, id: 'sw-update' }
    );
  },
  onOfflineReady: () => {
    toast.success('Gnosis is ready to work offline.', { id: 'sw-ready', duration: 4000 });
  },
});

export default function App() {
  // Wire offline/sync state into the toast system
  const handleToast = useCallback(
    (message: string, variant: 'info' | 'success' | 'warning') => {
      if (variant === 'success') toast.success(message, { duration: 4000 });
      else if (variant === 'warning') toast(message, { icon: '⚠️', duration: Infinity });
      else toast(message, { duration: 4000 });
    },
    []
  );

  const { isOnline, queuedCount, triggerSync } = useOfflineSync(handleToast);

  return (
    <BrowserRouter>
      {/* Offline banner sits above everything, sticky to the top */}
      <OfflineBanner
        isOnline={isOnline}
        queuedCount={queuedCount}
        onSyncClick={triggerSync}
      />

      <React.Suspense
        fallback={
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100dvh',
              color: 'var(--color-text-muted)',
              fontSize: 'var(--text-sm)',
            }}
          >
            Loading…
          </div>
        }
      >
        <Routes>
          <Route path="/login"         element={<LoginPage />} />
          <Route path="/"              element={<NotesPage />} />
          <Route path="/notes/:id"     element={<NoteEditorPage />} />
          <Route path="/graph"         element={<GraphPage />} />
          <Route path="/search"        element={<SearchPage />} />
          <Route path="/ai"            element={<AIPage />} />
          <Route path="/settings"      element={<SettingsPage />} />
          <Route path="/query"         element={<QueryPage />} />
          <Route path="*"              element={<Navigate to="/" replace />} />
        </Routes>
      </React.Suspense>

      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: 'var(--color-surface-2)',
            color:      'var(--color-text)',
            border:     '1px solid var(--color-border)',
            fontSize:   'var(--text-sm)',
          },
        }}
      />
    </BrowserRouter>
  );
}
