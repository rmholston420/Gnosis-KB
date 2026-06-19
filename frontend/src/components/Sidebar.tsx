import { NavLink } from 'react-router-dom';
import {
  BookOpen, Search, GitBranch, MessageSquare,
  Upload, CalendarDays, Settings, ChevronLeft, ChevronRight,
  Inbox
} from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

const PARA_FOLDERS = [
  { id: '00-inbox', label: 'Inbox' },
  { id: '10-zettelkasten', label: 'Zettelkasten' },
  { id: '20-projects', label: 'Projects' },
  { id: '30-areas', label: 'Areas' },
  { id: '40-resources', label: 'Resources' },
  { id: '50-archive', label: 'Archive' },
  { id: '60-journals', label: 'Journals' },
  { id: '70-sources', label: 'Sources' },
  { id: '80-meta', label: 'Meta' },
];

const NAV_ITEMS = [
  { to: '/notes', label: 'Notes', icon: BookOpen },
  { to: '/graph', label: 'Graph', icon: GitBranch },
  { to: '/search', label: 'Search', icon: Search },
  { to: '/chat', label: 'AI Chat', icon: MessageSquare },
  { to: '/ingest', label: 'Ingest', icon: Upload },
  { to: '/daily', label: 'Daily', icon: CalendarDays },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebar, setActiveFolder, activeFolder } = useAppStore();

  return (
    <aside
      className="fixed top-0 left-0 h-full bg-bg-secondary border-r border-border flex flex-col z-30 transition-all duration-200"
      style={{ width: sidebarCollapsed ? '48px' : '260px' }}
    >
      {/* Logo + collapse */}
      <div className="h-12 flex items-center justify-between px-3 border-b border-border flex-shrink-0">
        {!sidebarCollapsed && (
          <span className="font-semibold text-text-primary text-sm tracking-wide">Gnosis KB</span>
        )}
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded hover:bg-bg-tertiary text-text-secondary transition-colors ml-auto"
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto py-2 no-scrollbar">
        {/* Main nav */}
        <div className="space-y-0.5 px-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-2 py-1.5 rounded text-sm transition-colors ${
                  isActive
                    ? 'bg-bg-tertiary text-text-primary'
                    : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary'
                }`
              }
            >
              <Icon size={15} className="flex-shrink-0" />
              {!sidebarCollapsed && <span>{label}</span>}
            </NavLink>
          ))}
        </div>

        {/* PARA folders */}
        {!sidebarCollapsed && (
          <div className="mt-4 px-2">
            <p className="text-xs font-semibold text-text-muted uppercase tracking-wider px-2 mb-1.5">
              Folders
            </p>
            {PARA_FOLDERS.map((folder) => (
              <button
                key={folder.id}
                onClick={() => setActiveFolder(activeFolder === folder.id ? null : folder.id)}
                className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm transition-colors ${
                  activeFolder === folder.id
                    ? 'bg-bg-elevated text-text-primary'
                    : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary'
                }`}
              >
                <Inbox size={13} className="flex-shrink-0" />
                <span className="truncate">{folder.label}</span>
              </button>
            ))}
          </div>
        )}
      </nav>
    </aside>
  );
}
