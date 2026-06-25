import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate, useLocation, Outlet } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster, toast } from 'react-hot-toast';
import Sidebar from '@/components/Sidebar';
import { useVaultWebSocket } from '@/hooks/useWebSocket';
import CommandPalette from '@/components/CommandPalette';
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
// ── Previously orphaned pages — now wired in ──────────────────────────────────
const AnalyticsPage     = lazy(() => import('@/pages/AnalyticsPage'));
const MocPage           = lazy(() => import('@/pages/MocPage'));
const QueryPage         = lazy(() => import('@/pages/QueryPage'));
const ReviewPage        = lazy(() => import('@/pages/ReviewPage'));
const IngestPage        = lazy(() => import('@/pages/IngestPage'));
const PluginsPage       = lazy(() => import('@/pages/PluginsPage'));
const TemplatesPage     = lazy(() => import('@/pages/TemplatesPage'));
const SyncPage          = lazy(() => import('@/pages/SyncPage'));

// ── Auth guard ────────────────────────────────────────────────────────────────
function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('gnosis_token');
  const location = useLocation();
  if (!token) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}

// ── Auth layout — no sidebar, full-screen (used by /login and /register) ──────
function AuthLayout() {
  return (
    <Suspense fallback={null}>
      <Outlet />
    </Suspense>
  );
}

// ── App shell — sidebar + main content (used by all protected routes) ─────────
function AppShell() {
  useVaultWebSocket();
  return (
    <div className="flex h-screen bg-gnosis-bg text-gnosis-fg overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Suspense fallback={<div className="p-8 text-gnosis-muted">Loading…</div>}>
          <Outlet />
        </Suspense>
      </main>
      {/* CommandPalette lives outside Suspense — no flash when ⌘K is pressed */}
      <CommandPalette />
      <Toaster position="bottom-right" />
    </div>
  );
}

// ── All routes (exported for testing) ────────────────────────────────────────
export function AppRoutes() {
  return (
    <Routes>
      {/* ── Public routes — no sidebar ── */}
      <Route element={<AuthLayout />}>
        <Route path="/login"    element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      {/* ── Protected routes — with sidebar ── */}
      <Route element={<PrivateRoute><AppShell /></PrivateRoute>}>
        <Route path="/"           element={<NotesPage />} />
        <Route path="/notes/new"  element={<NoteEditorPage />} />
        <Route path="/notes/:id"  element={<NoteEditorPage />} />
        <Route path="/editor/:id" element={<NoteEditorPage />} />
        <Route path="/search"     element={<SearchPage />} />
        <Route path="/graph"      element={<GraphPage />} />
        <Route path="/ai"         element={<AiPage />} />
        <Route path="/daily"      element={<DailyNotePage />} />
        <Route path="/tags"       element={<TagsPage />} />
        <Route path="/backlinks"  element={<BacklinksPage />} />
        <Route path="/vault-sync" element={<VaultSyncPage />} />
        <Route path="/settings"   element={<SettingsPage />} />
        {/* Previously orphaned pages */}
        <Route path="/analytics"  element={<AnalyticsPage />} />
        <Route path="/moc"        element={<MocPage />} />
        <Route path="/query"      element={<QueryPage />} />
        <Route path="/review"     element={<ReviewPage />} />
        <Route path="/ingest"     element={<IngestPage />} />
        <Route path="/plugins"    element={<PluginsPage />} />
        <Route path="/templates"  element={<TemplatesPage />} />
        <Route path="/sync"       element={<SyncPage />} />
      </Route>

      {/* ── Catch-all ── */}
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
      <AppRoutes />
    </QueryClientProvider>
  );
}
