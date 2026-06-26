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
const AnalyticsPage     = lazy(() => import('@/pages/AnalyticsPage'));
const MocPage           = lazy(() => import('@/pages/MocPage'));
const QueryPage         = lazy(() => import('@/pages/QueryPage'));
const ReviewPage        = lazy(() => import('@/pages/ReviewPage'));
const IngestPage        = lazy(() => import('@/pages/IngestPage'));
const PluginsPage       = lazy(() => import('@/pages/PluginsPage'));
const TemplatesPage     = lazy(() => import('@/pages/TemplatesPage'));
const SyncPage          = lazy(() => import('@/pages/SyncPage'));
// AIChatPage is a thin re-export of AiPage (see AIChatPage.tsx)
const AIChatPage        = lazy(() => import('@/pages/AIChatPage'));

// ── Auth-required probe ───────────────────────────────────────────────────────
// Probe a PROTECTED endpoint. If it returns 401 without a token, auth is
// required. If it returns 200, the backend is running with AUTH_REQUIRED=false.
//
// We intentionally probe /api/v1/notes/ (a real protected route) rather than
// /health/ping (a public endpoint that always returns 200, which caused the
// probe to always report auth NOT required regardless of server config).
let _authRequired: boolean | null = null;
let _probePromise: Promise<boolean> | null = null;

/** Exported for test isolation — resets cached probe state between test runs. */
export function _resetAuthProbeForTests(): void {
  _authRequired = null;
  _probePromise = null;
}

function probeAuthRequired(): Promise<boolean> {
  if (_authRequired !== null) return Promise.resolve(_authRequired);
  if (_probePromise) return _probePromise;

  const BASE =
    (import.meta as { env?: { VITE_API_BASE_URL?: string } }).env?.VITE_API_BASE_URL ?? '/api/v1';

  // Probe the notes collection endpoint without a token.
  // 401 → auth IS required; 200 → auth is NOT required.
  // Any other outcome (network error, 5xx) → default safe: require auth.
  _probePromise = fetch(`${BASE}/notes/`, { method: 'GET' })
    .then((res) => {
      const required = res.status === 401;
      _authRequired = required;
      return required;
    })
    .catch(() => {
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

  if (authRequired === null) {
    return <div className="flex h-screen items-center justify-center text-gnosis-muted">Loading…</div>;
  }

  if (!authRequired) {
    return <>{children}</>;
  }

  const token = localStorage.getItem('gnosis_token');
  if (!token) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}

// ── Error boundary to prevent WS / lazy-load crashes from killing the shell ──
type EBState = { hasError: boolean; message: string };
class ShellErrorBoundary extends React.Component<
  { children: React.ReactNode },
  EBState
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, message: '' };
  }
  static getDerivedStateFromError(err: unknown): EBState {
    return { hasError: true, message: String(err) };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex h-screen flex-col items-center justify-center gap-4 p-8 text-gnosis-muted">
          <p className="text-gnosis-error font-semibold">Something went wrong.</p>
          <p className="text-sm opacity-70">{this.state.message}</p>
          <button
            className="rounded px-4 py-2 bg-gnosis-accent text-white text-sm"
            onClick={() => this.setState({ hasError: false, message: '' })}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── Auth layout — no sidebar, full-screen ─────────────────────────────────────
function AuthLayout() {
  return (
    <Suspense fallback={null}>
      <Outlet />
    </Suspense>
  );
}

// ── App shell — sidebar + main content ───────────────────────────────────────
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
      <CommandPalette />
      <Toaster position="bottom-right" />
    </div>
  );
}

// ── All routes (exported for testing) ────────────────────────────────────────
export function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route element={<AuthLayout />}>
        <Route path="/login"    element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      {/* Protected routes */}
      <Route element={<PrivateRoute><ShellErrorBoundary><AppShell /></ShellErrorBoundary></PrivateRoute>}>
        <Route path="/"           element={<NotesPage />} />
        <Route path="/notes/new"  element={<NoteEditorPage />} />
        <Route path="/notes/:id"  element={<NoteEditorPage />} />
        <Route path="/editor/:id" element={<NoteEditorPage />} />
        <Route path="/search"     element={<SearchPage />} />
        <Route path="/graph"      element={<GraphPage />} />
        <Route path="/ai"         element={<AiPage />} />
        <Route path="/ai/chat"    element={<AIChatPage />} />
        <Route path="/daily"      element={<DailyNotePage />} />
        <Route path="/tags"       element={<TagsPage />} />
        <Route path="/backlinks"  element={<BacklinksPage />} />
        <Route path="/vault-sync" element={<VaultSyncPage />} />
        <Route path="/settings"   element={<SettingsPage />} />
        <Route path="/analytics"  element={<AnalyticsPage />} />
        <Route path="/moc"        element={<MocPage />} />
        <Route path="/query"      element={<QueryPage />} />
        <Route path="/review"     element={<ReviewPage />} />
        <Route path="/ingest"     element={<IngestPage />} />
        <Route path="/plugins"    element={<PluginsPage />} />
        <Route path="/templates"  element={<TemplatesPage />} />
        <Route path="/sync"       element={<SyncPage />} />
      </Route>

      {/*
        FIX: NotFoundPage was lazy-loaded but had no Suspense boundary.
        The catch-all sits outside AppShell's Suspense, so if the lazy
        bundle hadn't loaded yet React threw an unhandled suspense error.
        Wrapped in its own Suspense with a null fallback.
      */}
      <Route
        path="*"
        element={
          <Suspense fallback={null}>
            <NotFoundPage />
          </Suspense>
        }
      />
    </Routes>
  );
}

// ── App root ──────────────────────────────────────────────────────────────────
export default function App() {
  // FIX: was useRef<QueryClient | null> initialized inline during render phase.
  // In React 18 Strict Mode the component runs twice; useState with an initializer
  // guarantees exactly one QueryClient instance per component mount.
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
      }),
  );

  useEffect(() => {
    // Guard: registerSW must run inside a lifecycle, not at module level.
    // Calling it at module scope fires in jsdom during tests (no SW support)
    // and emits uncaught promise rejections that fail the test suite.
    if (typeof window !== 'undefined' && 'serviceWorker' in navigator) {
      registerSW({
        onNeedRefresh() {
          toast('A new version is available. Refresh to update.');
        },
        onOfflineReady() {
          toast.success('App is ready to work offline.');
        },
      });
    }
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <AppRoutes />
    </QueryClientProvider>
  );
}
