import { useNavigate } from 'react-router-dom';
import { Search, Plus, Moon } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

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
      <div className="flex-1 flex items-center gap-2 bg-bg-tertiary rounded px-3 py-1.5 max-w-lg">
        <Search size={14} className="text-text-muted flex-shrink-0" />
        <input
          type="text"
          placeholder="Search vault... (Enter)"
          className="bg-transparent text-sm text-text-primary placeholder-text-muted outline-none flex-1 min-w-0"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={handleSearch}
        />
      </div>
      <button
        onClick={() => navigate('/notes/new')}
        className="flex items-center gap-1.5 px-3 py-1.5 bg-accent-blue hover:bg-blue-600 text-white text-sm rounded transition-colors"
      >
        <Plus size={14} />
        <span className="hidden sm:inline">New Note</span>
      </button>
    </header>
  );
}
