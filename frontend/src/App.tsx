import React, { Suspense, lazy, useEffect, useRef, useState } from 'react';
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

// ── Auth-required probe ───────────────────────────────────────────────────────
// We ask the backend once whether AUTH_REQUIRED is true.  The result is cached
// in a module-level variable so every PrivateRoute instance shares it without
// an extra network call.
//
// The probe hits GET /api/v1/health/ping — a guaranteed-public endpoint that
// returns {"status":"ok"}.  If the request succeeds without a token we know
// auth is not required and we skip the localStorage gate.
//
// Three states:
//   null    = probe not yet complete (show nothing / spinner)
//   true    = backend requires a real JWT token
//   false   = backend is open (AUTH_REQUIRED=false)
let _authRequired: boolean | null = null;
let _probePromise: Promise<boolean> | null = null;

function probeAuthRequired(): Promise<boolean> {
  if (_authRequired !== null) return Promise.resolve(_authRequired);
  if (_probePromise) return _probePromise;

  const BASE =
    (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ?? '/api/v1';

  _probePromise = fetch(`${BASE}/health/ping`, { method: 'GET' })
    .then((res) => {
      // If we get 200 without a token, auth is not required.
      // If we get 401, auth IS required.
      // Any other status (network error, 500): default to "auth required"
      // so we don't accidentally expose the app.
      const required = res.status === 401;
      _authRequired = required;
      return required;
    })
    .catch(() => {
      // Network error — default safe: require auth
      _authRequired = true;
      return true;
    });

  return _probePromise;
}

// ── Auth guard ────────────────────────────────────────────────────────────────
function PrivateRoute({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const [authRequired, setAuthRequired] = useState<boolean | null>(_authRequired);
  const probed = useRef(false);

  useEffect(() => {
    if (probed.current) return;
    probed.current = true;
    probeAuthRequired().then(setAuthRequired);
  }, []);

  // Still probing — render nothing to avoid a flash redirect to /login
  if (authRequired === null) {
    return <div className="flex h-screen items-center justify-center text-gnosis-muted">Loading…</div>;
  }

  // Backend does NOT require auth — bypass the token check entirely.
  // The backend will still enforce ownership scoping; the frontend just
  // doesn't need a stored token to navigate.
  if (!authRequired) {
    return <>{children}</>;
  }

  // Backend DOES require auth — enforce the token gate as before.
  const token = localStorage.getItem('gnosis_token');
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
