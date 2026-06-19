import React from 'react';
import { Routes, Route, NavLink } from 'react-router-dom';
import { BookOpen, Search, GitBranch, RotateCcw, Settings, Table2, Network } from 'lucide-react';
import NotesPage from './pages/NotesPage';
import NoteEditor from './pages/NoteEditor';
import SearchPage from './pages/SearchPage';
import ReviewPage from './pages/ReviewPage';
import GraphPage from './pages/GraphPage';
import SettingsPage from './pages/SettingsPage';
import QueryPage from './pages/QueryPage';
import MocPage from './pages/MocPage';

const navItems = [
  { to: '/', icon: BookOpen, label: 'Notes' },
  { to: '/search', icon: Search, label: 'Search' },
  { to: '/graph', icon: GitBranch, label: 'Graph' },
  { to: '/query', icon: Table2, label: 'Query' },
  { to: '/moc', icon: Network, label: 'MOC' },
  { to: '/review', icon: RotateCcw, label: 'Review' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export default function App() {
  return (
    <div className="flex h-screen bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100">
      {/* Sidebar nav */}
      <nav className="flex w-14 flex-col items-center gap-1 border-r border-gray-200 dark:border-gray-800 py-4">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            title={label}
            end={to === '/'}
            className={({ isActive }) =>
              `flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${
                isActive
                  ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400'
                  : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
              }`
            }
          >
            <Icon size={20} />
          </NavLink>
        ))}
      </nav>

      {/* Main content */}
      <main className="flex flex-1 overflow-hidden">
        <Routes>
          <Route path="/" element={<NotesPage />} />
          <Route path="/notes/:id" element={<NoteEditor />} />
          <Route path="/notes/new" element={<NoteEditor />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/query" element={<QueryPage />} />
          <Route path="/moc" element={<MocPage />} />
          <Route path="/review" element={<ReviewPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
