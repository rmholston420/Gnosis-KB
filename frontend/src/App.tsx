import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import NotesPage from './pages/NotesPage';
import NoteEditorPage from './pages/NoteEditorPage';
import GraphPage from './pages/GraphPage';
import SearchPage from './pages/SearchPage';
import AIChatPage from './pages/AIChatPage';
import IngestPage from './pages/IngestPage';
import DailyNotePage from './pages/DailyNotePage';
import SettingsPage from './pages/SettingsPage';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<NotesPage />} />
        <Route path="notes" element={<NotesPage />} />
        <Route path="notes/new" element={<NoteEditorPage />} />
        <Route path="notes/:id" element={<NoteEditorPage />} />
        <Route path="graph" element={<GraphPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="chat" element={<AIChatPage />} />
        <Route path="ingest" element={<IngestPage />} />
        <Route path="daily" element={<DailyNotePage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
