import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Plus, Command } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import { ThemeToggle } from './layout/ThemeToggle';

export default function TopBar() {
  const navigate = useNavigate();
  const { searchQuery, setSearchQuery } = useAppStore();

  const handleSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery)}`);
    }
  };

  return (
    <header className="h-12 flex items-center gap-3 px-4 border-b border-border bg-bg-secondary flex-shrink-0">
      {/* Search box */}
      <div className="flex-1 flex items-center gap-2 bg-bg-tertiary rounded px-3 py-1.5 max-w-lg">
        <Search size={14} className="text-text-muted flex-shrink-0" />
        <input
          type="text"
          placeholder="Search vault\u2026 (Enter)"
          className="bg-transparent text-sm text-text-primary placeholder-text-muted outline-none flex-1 min-w-0"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={handleSearch}
        />
        {/* Keyboard shortcut hint */}
        <kbd className="hidden sm:inline text-xs text-text-muted bg-bg-elevated rounded px-1 py-0.5 font-mono">
          \u23ce
        </kbd>
      </div>

      {/* Command palette shortcut */}
      <button
        onClick={() => navigate('/search')}
        className="p-1.5 rounded text-text-muted hover:text-text-primary hover:bg-bg-elevated transition-colors"
        title="Command palette (\u2318K)"
        aria-label="Open command palette"
      >
        <Command size={15} />
      </button>

      {/* Theme toggle */}
      <ThemeToggle />

      {/* New note */}
      <button
        onClick={() => navigate('/notes/new')}
        className="flex items-center gap-1.5 px-3 py-1.5 text-white text-sm rounded transition-opacity hover:opacity-80"
        style={{ backgroundColor: '#1f6feb' }}
      >
        <Plus size={14} />
        <span className="hidden sm:inline">New Note</span>
      </button>
    </header>
  );
}
