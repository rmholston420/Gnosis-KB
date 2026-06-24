/**
 * CommandPalette — ⌘K / Ctrl+K command palette using cmdk.
 * Allows users to:
 *   - Quick-jump to any note by title
 *   - Navigate to top-level pages
 *   - Create a new note
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Command } from 'cmdk';
import { useNavigate } from 'react-router-dom';
import { FileText, Plus, Home, Search, GitBranch, Brain, BookOpen, Hash, Zap, Settings, X } from 'lucide-react';
import { useNotes } from '../hooks/useNotes';
import type { Note } from '../types';

interface CommandPaletteProps {
  open:    boolean;
  onClose: () => void;
}

const PAGES = [
  { href: '/',         label: 'Notes',    icon: <Home      size={13} /> },
  { href: '/search',   label: 'Search',   icon: <Search    size={13} /> },
  { href: '/graph',    label: 'Graph',    icon: <GitBranch size={13} /> },
  { href: '/review',   label: 'Review',   icon: <Brain     size={13} /> },
  { href: '/daily',    label: 'Daily',    icon: <BookOpen  size={13} /> },
  { href: '/tags',     label: 'Tags',     icon: <Hash      size={13} /> },
  { href: '/ai',       label: 'AI Chat',  icon: <Zap       size={13} /> },
  { href: '/settings', label: 'Settings', icon: <Settings  size={13} /> },
];

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate   = useNavigate();
  const [query, setQuery] = useState('');
  const { data }   = useNotes();
  const notes: Note[] = (data?.items ?? []) as Note[];

  // Reset query when palette opens
  useEffect(() => { if (open) setQuery(''); }, [open]);

  const goTo = useCallback((href: string) => {
    navigate(href);
    onClose();
  }, [navigate, onClose]);

  if (!open) return null;

  // Filter notes by query
  const filteredNotes = query.trim()
    ? notes.filter((n) => n.title.toLowerCase().includes(query.toLowerCase()))
    : notes.slice(0, 8);

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4"
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      {/* Overlay */}
      <div className="absolute inset-0 bg-black/60" />

      {/* Panel */}
      <div className="relative w-full max-w-xl bg-bg-secondary border border-border rounded-xl shadow-2xl overflow-hidden z-10">
        <Command shouldFilter={false}>
          {/* Input */}
          <div className="flex items-center gap-2 px-3 py-2 border-b border-border">
            <Search size={14} className="text-text-muted flex-shrink-0" />
            <Command.Input
              autoFocus
              placeholder="Search notes or jump to a page\u2026"
              value={query}
              onValueChange={setQuery}
              className="flex-1 bg-transparent text-sm text-text-primary placeholder-text-muted outline-none"
            />
            <button onClick={onClose} className="text-text-muted hover:text-text-primary transition-colors p-1">
              <X size={13} />
            </button>
          </div>

          {/* Results */}
          <Command.List className="max-h-80 overflow-y-auto py-1">
            <Command.Empty className="text-xs text-text-muted text-center py-6">
              No results.
            </Command.Empty>

            {/* New note action */}
            <Command.Group heading="Actions" className="[&>div[cmdk-group-heading]]:text-xs [&>div[cmdk-group-heading]]:text-text-muted [&>div[cmdk-group-heading]]:px-3 [&>div[cmdk-group-heading]]:py-1.5">
              <Command.Item
                value="new-note"
                onSelect={() => goTo('/notes/new')}
                className="flex items-center gap-2.5 px-3 py-2 text-sm text-text-primary cursor-pointer data-[selected=true]:bg-bg-elevated hover:bg-bg-elevated transition-colors"
              >
                <Plus size={13} className="text-accent-cyan" />
                New note
              </Command.Item>
            </Command.Group>

            {/* Pages */}
            <Command.Group heading="Pages" className="[&>div[cmdk-group-heading]]:text-xs [&>div[cmdk-group-heading]]:text-text-muted [&>div[cmdk-group-heading]]:px-3 [&>div[cmdk-group-heading]]:py-1.5">
              {PAGES
                .filter((p) => !query.trim() || p.label.toLowerCase().includes(query.toLowerCase()))
                .map((p) => (
                  <Command.Item
                    key={p.href}
                    value={p.href}
                    onSelect={() => goTo(p.href)}
                    className="flex items-center gap-2.5 px-3 py-2 text-sm text-text-muted cursor-pointer data-[selected=true]:bg-bg-elevated hover:bg-bg-elevated transition-colors"
                  >
                    <span className="text-text-muted">{p.icon}</span>
                    {p.label}
                  </Command.Item>
                ))}
            </Command.Group>

            {/* Notes */}
            {filteredNotes.length > 0 && (
              <Command.Group heading="Notes" className="[&>div[cmdk-group-heading]]:text-xs [&>div[cmdk-group-heading]]:text-text-muted [&>div[cmdk-group-heading]]:px-3 [&>div[cmdk-group-heading]]:py-1.5">
                {filteredNotes.map((note) => (
                  <Command.Item
                    key={note.note_id ?? note.id}
                    value={note.note_id ?? note.id}
                    onSelect={() => goTo(`/notes/${note.note_id ?? note.id}`)}
                    className="flex items-center gap-2.5 px-3 py-2 text-sm text-text-primary cursor-pointer data-[selected=true]:bg-bg-elevated hover:bg-bg-elevated transition-colors"
                  >
                    <FileText size={13} className="text-text-muted flex-shrink-0" />
                    <span className="truncate">{note.title}</span>
                    {note.folder && (
                      <span className="ml-auto text-xs text-text-muted truncate max-w-[100px]">{note.folder}</span>
                    )}
                  </Command.Item>
                ))}
              </Command.Group>
            )}
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
