import React, { useCallback, useEffect, useRef } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Toaster, toast } from 'react-hot-toast';

import Layout                      from '@/components/Layout';
import { OfflineBanner }           from '@/components/OfflineBanner';
import { useOfflineSync }          from '@/hooks/useOfflineSync';
import { registerSW, skipWaiting } from '@/registerSW';
import { useVaultWebSocket }       from '@/hooks/useWebSocket';
import { useQueryClient }          from '@tanstack/react-query';

// Pages — lazy loaded
const LoginPage      = React.lazy(() => import('@/pages/LoginPage'));
const NotesPage      = React.lazy(() => import('@/pages/NotesPage'));
const NoteEditorPage = React.lazy(() => import('@/pages/NoteEditorPage'));
const GraphPage      = React.lazy(() => import('@/pages/GraphPage'));
const SearchPage     = React.lazy(() => import('@/pages/SearchPage'));
const AIPage         = React.lazy(() => import('@/pages/AIChatPage'));
const SettingsPage   = React.lazy(() => import('@/pages/SettingsPage'));
const QueryPage      = React.lazy(() => import('@/pages/QueryPage'));
const DailyNotePage  = React.lazy(() => import('@/pages/DailyNotePage'));
const ReviewPage     = React.lazy(() => import('@/pages/ReviewPage'));
const IngestPage     = React.lazy(() => import('@/pages/IngestPage'));
const MocPage        = React.lazy(() => import('@/pages/MocPage'));
const TagsPage       = React.lazy(() => import('@/pages/TagsPage'));
const CommandPalette = React.lazy(() =>
  import('@/components/CommandPalette').then((m) => ({ default: m.CommandPalette })),
);

registerSW({
  onNeedRefresh: () => {
    toast(
      (t) => (
        <span>
          A new version of Gnosis is available.{' '}
          <button
            onClick={() => { skipWaiting(); toast.dismiss(t.id); }}
            style={{ fontWeight: 600, textDecoration: 'underline', cursor: 'pointer' }}
          >
            Reload now
          </button>
        </span>
      ),
      { duration: Infinity, id: 'sw-update' },
    );
  },
  onOfflineReady: () => {
    toast.success('Gnosis is ready to work offline.', { id: 'sw-ready', duration: 4000 });
  },
});

/** Redirect to /login if no JWT in localStorage. */
function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('gnosis_token');
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

const Fallback = (
  <div style={{
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    height: '100dvh', color: '#8b949e', fontSize: '0.875rem',
  }}>
    Loading…
  </div>
);

/** Wires the vault WebSocket so query caches are invalidated on push events. */
function VaultSyncWatcher() {
  const queryClient = useQueryClient();
  useVaultWebSocket((event) => {
    if (event.type === 'note_updated' || event.type === 'note_created') {
      queryClient.invalidateQueries({ queryKey: ['notes'] });
      queryClient.invalidateQueries({ queryKey: ['note', event.note_id] });
      queryClient.invalidateQueries({ queryKey: ['graph'] });
    }
    if (event.type === 'vault_synced') {
      queryClient.invalidateQueries();
    }
  });
  return null;
}

export function AppRoutes() {
  const [cmdOpen, setCmdOpen] = React.useState(false);

  // ⌘K / Ctrl+K global shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCmdOpen((v) => !v);
      }
      if (e.key === 'Escape') setCmdOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <>
      <VaultSyncWatcher />

      <React.Suspense fallback={Fallback}>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />

          {/* Protected — all wrapped in Layout (sidebar + topbar) */}
          <Route
            element={
              <PrivateRoute>
                <Layout />
              </PrivateRoute>
            }
          >
            <Route index                   element={<NotesPage />} />
            <Route path="/notes"           element={<NotesPage />} />
            <Route path="/notes/new"       element={<NoteEditorPage />} />
            <Route path="/notes/:id"       element={<NoteEditorPage />} />
            <Route path="/graph"           element={<GraphPage />} />
            <Route path="/search"          element={<SearchPage />} />
            <Route path="/ai"              element={<AIPage />} />
            <Route path="/settings"        element={<SettingsPage />} />
            <Route path="/query"           element={<QueryPage />} />
            <Route path="/daily"           element={<DailyNotePage />} />
            <Route path="/review"          element={<ReviewPage />} />
            <Route path="/ingest"          element={<IngestPage />} />
            <Route path="/moc"             element={<MocPage />} />
            <Route path="/tags"            element={<TagsPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </React.Suspense>

      {/* Command Palette overlay */}
      {cmdOpen && (
        <React.Suspense fallback={null}>
          <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
        </React.Suspense>
      )}

      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: '#21262d',
            color:      '#e6edf3',
            border:     '1px solid #30363d',
            fontSize:   '0.875rem',
          },
        }}
      />
    </>
  );
}

export default function App() {
  const handleToast = useCallback(
    (message: string, variant: 'info' | 'success' | 'warning') => {
      if (variant === 'success')       toast.success(message, { duration: 4000 });
      else if (variant === 'warning')  toast(message, { icon: '⚠️', duration: Infinity });
      else                             toast(message, { duration: 4000 });
    },
    [],
  );

  const { isOnline, queuedCount, triggerSync } = useOfflineSync(handleToast);

  return (
    <>
      <OfflineBanner isOnline={isOnline} queuedCount={queuedCount} onSyncClick={triggerSync} />
      <AppRoutes />
    </>
  );
}
