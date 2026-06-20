/**
 * Sidebar
 * =======
 * Primary navigation sidebar with collapsible state persisted to app store.
 * Nav items ordered by usage frequency; Tags link added in Slice 9.
 */
import { NavLink, useNavigate } from 'react-router-dom';
import {
  BookOpen, Brain, FileText, GitBranch, Hash,
  HelpCircle, Home, LogOut, Plus, Search,
  Settings, Upload, Zap,
} from 'lucide-react';
import { useAppStore } from '../store/useAppStore';

interface NavItem {
  to: string;
  icon: React.ReactNode;
  label: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/',        icon: <Home size={16} />,      label: 'Notes'     },
  { to: '/search',  icon: <Search size={16} />,    label: 'Search'    },
  { to: '/ai',      icon: <Zap size={16} />,        label: 'AI Chat'   },
  { to: '/graph',   icon: <GitBranch size={16} />, label: 'Graph'     },
  { to: '/tags',    icon: <Hash size={16} />,      label: 'Tags'      },
  { to: '/review',  icon: <Brain size={16} />,     label: 'Review'    },
  { to: '/daily',   icon: <BookOpen size={16} />,  label: 'Daily'     },
  { to: '/moc',     icon: <FileText size={16} />,  label: 'MOC'       },
  { to: '/query',   icon: <HelpCircle size={16} />, label: 'Query'    },
  { to: '/ingest',  icon: <Upload size={16} />,    label: 'Ingest'    },
  { to: '/settings',icon: <Settings size={16} />,  label: 'Settings'  },
];

import React from 'react';

export default function Sidebar() {
  const { sidebarCollapsed, setSidebarCollapsed } = useAppStore();
  const navigate = useNavigate();

  function handleLogout() {
    localStorage.removeItem('gnosis_token');
    navigate('/login');
  }

  return (
    <aside
      className={`flex flex-col border-r border-border bg-bg-secondary transition-all duration-200 ${
        sidebarCollapsed ? 'w-12' : 'w-48'
      }`}
    >
      {/* Logo / collapse toggle */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-border flex-shrink-0">
        {!sidebarCollapsed && (
          <span className="text-sm font-semibold text-text-primary tracking-tight">Gnosis</span>
        )}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="p-1 rounded hover:bg-bg-elevated text-text-muted hover:text-text-primary transition-colors"
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            {sidebarCollapsed
              ? <path d="M9 18l6-6-6-6" />
              : <path d="M15 18l-6-6 6-6" />}
          </svg>
        </button>
      </div>

      {/* New note shortcut */}
      <div className="px-2 py-2 border-b border-border flex-shrink-0">
        <button
          onClick={() => navigate('/notes/new')}
          className={`w-full flex items-center gap-2 px-2 py-1.5 rounded text-xs font-medium bg-accent-cyan/10 hover:bg-accent-cyan/20 text-accent-cyan transition-colors ${
            sidebarCollapsed ? 'justify-center' : ''
          }`}
          title="New note"
        >
          <Plus size={14} />
          {!sidebarCollapsed && 'New Note'}
        </button>
      </div>

      {/* Nav items */}
      <nav className="flex-1 overflow-y-auto py-2 space-y-0.5 px-1">
        {NAV_ITEMS.map(({ to, icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-2 py-1.5 rounded text-xs transition-colors ${
                isActive
                  ? 'bg-bg-elevated text-text-primary font-medium'
                  : 'text-text-muted hover:text-text-primary hover:bg-bg-elevated'
              } ${sidebarCollapsed ? 'justify-center' : ''}`
            }
            title={sidebarCollapsed ? label : undefined}
          >
            {icon}
            {!sidebarCollapsed && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Logout */}
      <div className="px-1 py-2 border-t border-border flex-shrink-0">
        <button
          onClick={handleLogout}
          className={`w-full flex items-center gap-2.5 px-2 py-1.5 rounded text-xs text-text-muted hover:text-red-400 hover:bg-red-500/10 transition-colors ${
            sidebarCollapsed ? 'justify-center' : ''
          }`}
          title="Log out"
        >
          <LogOut size={14} />
          {!sidebarCollapsed && 'Log out'}
        </button>
      </div>
    </aside>
  );
}
