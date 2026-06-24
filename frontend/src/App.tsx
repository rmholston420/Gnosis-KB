/**
 * App.tsx — root shell.
 * Adds:
 *  1. Global ⌘K / Ctrl+K shortcut → commandPaletteStore.toggle()
 *  2. useVaultWebSocket() mounted once so live sync events reach every page
 */
import React, { useEffect } from 'react';
import { Routes, Route } from 'react-router-dom';
import Layout from './components/layout/Layout';
import { CommandPalette } from './components/shared/CommandPalette';
import { useCommandPaletteStore } from './store/editorStore';
import { useVaultWebSocket } from './hooks/useWebSocket';

const NotesPage      = React.lazy(() => import('./pages/NotesPage'));
const NoteEditorPage = React.lazy(() => import('./pages/NoteEditorPage'));
const GraphPage      = React.lazy(() => import('./pages/GraphPage'));
const SearchPage     = React.lazy(() => import('./pages/SearchPage'));
const DailyNotePage  = React.lazy(() => import('./pages/DailyNotePage'));
const AiPage         = React.lazy(() => import('./pages/AiPage'));
const SettingsPage   = React.lazy(() => import('./pages/SettingsPage'));
const TagsPage       = React.lazy(() => import('./pages/TagsPage'));
const TemplatesPage  = React.lazy(() => import('./pages/TemplatesPage'));
const PluginsPage    = React.lazy(() => import('./pages/PluginsPage'));
const SyncPage       = React.lazy(() => import('./pages/SyncPage'));
const AnalyticsPage  = React.lazy(() => import('./pages/AnalyticsPage'));
const NotFoundPage   = React.lazy(() => import('./pages/NotFoundPage'));

export default function App() {
  const { toggle } = useCommandPaletteStore();

  // ⌘K / Ctrl+K global shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        toggle();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [toggle]);

  // Live vault sync events
  useVaultWebSocket();

  return (
    <>
      <React.Suspense fallback={<div className="flex h-screen items-center justify-center text-gnosis-muted text-sm">Loading…</div>}>
        <Routes>
          <Route element={<Layout />}>
            <Route index            element={<NotesPage />} />
            <Route path="notes"     element={<NotesPage />} />
            <Route path="notes/new" element={<NoteEditorPage />} />
            <Route path="notes/:id" element={<NoteEditorPage />} />
            <Route path="graph"     element={<GraphPage />} />
            <Route path="search"    element={<SearchPage />} />
            <Route path="daily"     element={<DailyNotePage />} />
            <Route path="ai"        element={<AiPage />} />
            <Route path="settings"  element={<SettingsPage />} />
            <Route path="tags"      element={<TagsPage />} />
            <Route path="templates" element={<TemplatesPage />} />
            <Route path="plugins"   element={<PluginsPage />} />
            <Route path="sync"      element={<SyncPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="*"         element={<NotFoundPage />} />
          </Route>
        </Routes>
      </React.Suspense>
      <CommandPalette />
    </>
  );
}
