/**
 * App.tsx
 * =======
 * Root application shell.
 *
 * Responsibilities:
 *  - BrowserRouter + route tree
 *  - QueryClientProvider + devtools (dev only)
 *  - Global ⌘K / Ctrl+K → CommandPalette
 *  - VaultSyncWatcher mounted here (invisible, subscribes to WebSocket)
 *  - ProtectedRoute wraps all authenticated views
 */
import React, { useCallback, useEffect, useState, lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';

// Layout + shared
import { Layout }            from './components/Layout';
import { CommandPalette }    from './components/CommandPalette';
import { VaultSyncWatcher }  from './components/VaultSyncWatcher';
import { ProtectedRoute }    from './components/ProtectedRoute';

// Pages
import LoginPage       from './pages/LoginPage';
import NotesPage       from './pages/NotesPage';
import NoteEditorPage  from './pages/NoteEditorPage';
import SearchPage      from './pages/SearchPage';
import GraphPage       from './pages/GraphPage';
import QueryPage       from './pages/QueryPage';
import AIChatPage      from './pages/AIChatPage';
import ReviewPage      from './pages/ReviewPage';
import MocPage         from './pages/MocPage';
import DailyNotePage   from './pages/DailyNotePage';
import TagsPage        from './pages/TagsPage';
import IngestPage      from './pages/IngestPage';
import SettingsPage    from './pages/SettingsPage';

// Devtools — lazy-loaded in dev only so the package is never required in test/prod
const ReactQueryDevtools = import.meta.env.DEV
  ? lazy(() =>
      import('@tanstack/react-query-devtools').then((m) => ({
        default: m.ReactQueryDevtools,
      }))
    )
  : null;

export default function App() {
  const [cmdOpen, setCmdOpen] = useState(false);

  // Global ⌘K / Ctrl+K shortcut
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      setCmdOpen((o) => !o);
    }
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  return (
    <>
      {/* WebSocket cache invalidator — no UI */}
      <VaultSyncWatcher />

      {/* ⌘K command palette — portal-rendered above everything */}
      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />

      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected — wrapped in the sidebar layout */}
        <Route element={<ProtectedRoute />}>
          <Route element={<Layout />}>
            <Route index element={<Navigate to="/notes" replace />} />
            <Route path="notes"          element={<NotesPage />} />
            <Route path="notes/new"      element={<NoteEditorPage />} />
            <Route path="notes/:id"      element={<NoteEditorPage />} />
            <Route path="search"         element={<SearchPage />} />
            <Route path="graph"          element={<GraphPage />} />
            <Route path="query"          element={<QueryPage />} />
            <Route path="chat"           element={<AIChatPage />} />
            <Route path="review"         element={<ReviewPage />} />
            <Route path="moc"            element={<MocPage />} />
            <Route path="moc/:id"        element={<MocPage />} />
            <Route path="daily"          element={<DailyNotePage />} />
            <Route path="tags"           element={<TagsPage />} />
            <Route path="ingest"         element={<IngestPage />} />
            <Route path="settings"       element={<SettingsPage />} />
          </Route>
        </Route>

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/notes" replace />} />
      </Routes>

      {/* React Query Devtools — only rendered in development builds */}
      {ReactQueryDevtools && (
        <Suspense fallback={null}>
          <ReactQueryDevtools initialIsOpen={false} buttonPosition="bottom-right" />
        </Suspense>
      )}
    </>
  );
}
