import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster, toast } from 'react-hot-toast';
import Sidebar from '@/components/Sidebar';
import { useVaultWebSocket } from '@/hooks/useWebSocket';
import { registerSW } from '@/registerSW';

// ── Lazy-load every page so the initial bundle stays small ────────────────────
const NotesPage         = lazy(() => import('@/pages/NotesPage'));
const NoteEditorPage    = lazy(() => import('@/pages/NoteEditorPage'));
const SearchPage        = lazy(() => import('@/pages/SearchPage'));
const GraphPage         = lazy(() => import('@/pages/GraphPage'));
const AiPage            = lazy(() => import('@/pages/AiPage'));
const SettingsPage      = lazy(() => import('@/pages/SettingsPage'));
const LoginPage         = lazy(() => import('@/pages/LoginPage'));
const RegisterPage      = lazy(() => import('@/pages/RegisterPage'));
const DailyNotePage     = lazy(() => import('@/pages/DailyNotePage'));
const TagsPage          = lazy(() => import('@/pages/TagsPage'));
const BacklinksPage     = lazy(() => import('@/pages/BacklinksPage'));
const VaultSyncPage     = lazy(() => import('@/pages/VaultSyncPage'));
const NotFoundPage      = lazy(() => import('@/pages/NotFoundPage'));

// ── Auth guard ────────────────────────────────────────────────────────────────
function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('gnosis_token');
  const location = useLocation();
  if (!token) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}

// ── Inner shell (needs QueryClient context) ───────────────────────────────────
function AppShell() {
  useVaultWebSocket();
  return (
    <div className="flex h-screen bg-gnosis-bg text-gnosis-fg overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Suspense fallback={<div className="p-8 text-gnosis-muted">Loading…</div>}>
          <AppRoutes />
        </Suspense>
      </main>
      <Toaster position="bottom-right" />
    </div>
  );
}

// ── All routes (exported for testing) ────────────────────────────────────────
export function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login"    element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* Protected */}
      <Route path="/" element={<PrivateRoute><NotesPage /></PrivateRoute>} />
      <Route path="/notes/new" element={<PrivateRoute><NoteEditorPage /></PrivateRoute>} />
      <Route path="/notes/:id" element={<PrivateRoute><NoteEditorPage /></PrivateRoute>} />
      <Route path="/editor/:id" element={<PrivateRoute><NoteEditorPage /></PrivateRoute>} />
      <Route path="/search"   element={<PrivateRoute><SearchPage /></PrivateRoute>} />
      <Route path="/graph"    element={<PrivateRoute><GraphPage /></PrivateRoute>} />
      <Route path="/ai"       element={<PrivateRoute><AiPage /></PrivateRoute>} />
      <Route path="/daily"    element={<PrivateRoute><DailyNotePage /></PrivateRoute>} />
      <Route path="/tags"     element={<PrivateRoute><TagsPage /></PrivateRoute>} />
      <Route path="/backlinks" element={<PrivateRoute><BacklinksPage /></PrivateRoute>} />
      <Route path="/vault-sync" element={<PrivateRoute><VaultSyncPage /></PrivateRoute>} />
      <Route path="/settings" element={<PrivateRoute><SettingsPage /></PrivateRoute>} />

      {/* Catch-all */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

// ── App root ──────────────────────────────────────────────────────────────────
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

registerSW({
  onNeedRefresh() {
    toast('A new version is available. Refresh to update.');
  },
  onOfflineReady() {
    toast.success('App is ready to work offline.');
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppShell />
    </QueryClientProvider>
  );
}
