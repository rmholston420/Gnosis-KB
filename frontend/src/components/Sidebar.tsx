import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  Home,
  Search,
  Zap,
  GitBranch,
  Calendar,
  Tag,
  Link2,
  RefreshCw,
  Settings,
  ChevronLeft,
  ChevronRight,
  Plus,
} from 'lucide-react';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/',           icon: <Home size={16} />,      label: 'Notes' },
  { to: '/search',     icon: <Search size={16} />,    label: 'Search' },
  { to: '/ai',         icon: <Zap size={16} />,       label: 'AI Chat' },
  { to: '/graph',      icon: <GitBranch size={16} />, label: 'Graph' },
  { to: '/daily',      icon: <Calendar size={16} />,  label: 'Daily Note' },
  { to: '/tags',       icon: <Tag size={16} />,       label: 'Tags' },
  { to: '/backlinks',  icon: <Link2 size={16} />,     label: 'Backlinks' },
  { to: '/vault-sync', icon: <RefreshCw size={16} />, label: 'Vault Sync' },
  { to: '/settings',   icon: <Settings size={16} />,  label: 'Settings' },
];

export default function Sidebar() {
  // Default to EXPANDED so tests see labels on first render
  const [expanded, setExpanded] = useState(true);

  return (
    <aside
      className={`flex flex-col border-r border-gnosis-border bg-gnosis-surface
        transition-all duration-200 ${
          expanded ? 'w-56' : 'w-12'
        }`}
    >
      {/* Header: brand + toggle */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-gnosis-border flex-shrink-0">
        {expanded && (
          <span className="text-sm font-semibold text-gnosis-fg tracking-tight select-none">
            Gnosis
          </span>
        )}
        <button
          aria-label={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
          title={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
          onClick={() => setExpanded(!expanded)}
          className="p-1 rounded hover:bg-gnosis-hover text-gnosis-muted hover:text-gnosis-fg transition-colors"
        >
          {expanded ? (
            <ChevronLeft size={14} />
          ) : (
            <ChevronRight size={14} />
          )}
        </button>
      </div>

      {/* New Note button */}
      <div className="px-2 py-2 border-b border-gnosis-border flex-shrink-0">
        <NavLink
          to="/notes/new"
          aria-label="New Note"
          title="New note"
          className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs font-medium
            bg-gnosis-accent/10 hover:bg-gnosis-accent/20 text-gnosis-accent transition-colors
            ${ expanded ? '' : 'justify-center' }`}
        >
          <Plus size={14} />
          {expanded && <span>New Note</span>}
        </NavLink>
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto py-2 space-y-0.5 px-1">
        {NAV_ITEMS.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            title={label}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-2 py-1.5 rounded text-xs transition-colors
              ${ expanded ? '' : 'justify-center' }
              ${ isActive
                  ? 'bg-gnosis-hover text-gnosis-fg font-medium'
                  : 'text-gnosis-muted hover:text-gnosis-fg hover:bg-gnosis-hover'
              }`
            }
          >
            {icon}
            {expanded && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
