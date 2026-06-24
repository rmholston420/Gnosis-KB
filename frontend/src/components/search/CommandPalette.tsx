/**
 * CommandPalette — Global Cmd+K / Ctrl+K command palette.
 *
 * Supports two modes:
 *   - Uncontrolled (default): manages its own open/closed state via Cmd+K.
 *   - Controlled: caller passes `open` + `onClose` props (used by tests and
 *     App.tsx when it needs external toggle control).
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Command } from 'cmdk';
import { useNavigate } from 'react-router-dom';
import Fuse from 'fuse.js';
import { FileText, GitBranch, Plus, Search, Settings, Zap } from 'lucide-react';
import { fetchNoteStubs, type NoteStub } from '@/lib/noteStubs';

interface ActionItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  action: () => void;
  group: 'actions';
}

interface NoteItem {
  id: string;
  title: string;
  folder: string;
  group: 'notes';
}

type PaletteItem = ActionItem | NoteItem;

async function createQuickNote(navigate: ReturnType<typeof useNavigate>) {
  const base = import.meta.env.VITE_API_BASE_URL ?? '';
  try {
    const resp = await fetch(`${base}/api/v1/notes`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('gnosis_token') ?? ''}`,
      },
      body: JSON.stringify({
        title: 'New Note',
        body: '',
        folder: '00-inbox',
        note_type: 'fleeting',
      }),
    });
    if (resp.ok) {
      const note = (await resp.json()) as { id: string };
      navigate(`/editor/${note.id}`);
    }
  } catch {
    navigate('/editor/new');
  }
}

export interface CommandPaletteProps {
  /** When provided, the palette operates in controlled mode. */
  open?: boolean;
  onClose?: () => void;
}

export default function CommandPalette({ open: openProp, onClose }: CommandPaletteProps = {}) {
  const isControlled = openProp !== undefined;
  const [internalOpen, setInternalOpen] = useState(false);
  const open = isControlled ? openProp : internalOpen;

  const [query, setQuery] = useState('');
  const [notes, setNotes] = useState<NoteStub[]>([]);
  const [results, setResults] = useState<PaletteItem[]>([]);
  const fuseRef = useRef<Fuse<NoteStub> | null>(null);
  const navigate = useNavigate();

  // Fetch note stubs once on first open.
  // .catch(() => []) ensures any network/auth rejection is absorbed silently
  // rather than escaping as an unhandled promise rejection.
  useEffect(() => {
    if (open && notes.length === 0) {
      fetchNoteStubs()
        .then((stubs) => {
          setNotes(stubs);
          fuseRef.current = new Fuse(stubs, {
            keys: ['title', 'folder'],
            threshold: 0.35,
            includeScore: true,
          });
        })
        .catch(() => {
          // On error: leave notes as [], palette stays functional with actions only.
        });
    }
  }, [open, notes.length]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        if (isControlled) {
          if (open) {
            setQuery('');
            onClose?.();
          }
        } else {
          setInternalOpen((prev) => !prev);
        }
        return;
      }
      if (e.key === 'Escape' && open) {
        setQuery('');
        if (isControlled) {
          onClose?.();
        } else {
          setInternalOpen(false);
          onClose?.();
        }
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, isControlled, onClose]);

  const close = useCallback(() => {
    setQuery('');
    if (!isControlled) setInternalOpen(false);
    onClose?.();
  }, [isControlled, onClose]);

  const actions: ActionItem[] = [
    {
      id: 'new-note',
      label: 'New Note in Inbox',
      icon: <Plus size={16} />,
      action: () => { close(); void createQuickNote(navigate); },
      group: 'actions',
    },
    {
      id: 'go-graph',
      label: 'Open Knowledge Graph',
      icon: <GitBranch size={16} />,
      action: () => { close(); navigate('/graph'); },
      group: 'actions',
    },
    {
      id: 'go-search',
      label: 'Search Vault',
      icon: <Search size={16} />,
      action: () => { close(); navigate('/search'); },
      group: 'actions',
    },
    {
      id: 'go-ai-chat',
      label: 'Open AI Chat',
      icon: <Zap size={16} />,
      action: () => { close(); navigate('/ai-chat'); },
      group: 'actions',
    },
    {
      id: 'go-settings',
      label: 'Settings',
      icon: <Settings size={16} />,
      action: () => { close(); navigate('/settings'); },
      group: 'actions',
    },
  ];

  useEffect(() => {
    if (!query.trim()) {
      setResults(actions);
      return;
    }
    const noteResults: NoteItem[] = fuseRef.current
      ? fuseRef.current
          .search(query)
          .slice(0, 8)
          .map(({ item }) => ({
            id: item.id,
            title: item.title,
            folder: item.folder,
            group: 'notes' as const,
          }))
      : [];
    setResults([
      ...actions.filter((a) => a.label.toLowerCase().includes(query.toLowerCase())),
      ...noteResults,
    ]);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, notes]);

  if (!open) return null;

  return (
    <div
      className="command-palette-backdrop"
      onClick={close}
      role="presentation"
    >
      <div
        className="command-palette-container"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Command palette"
        aria-modal="true"
      >
        <Command label="Command palette" shouldFilter={false}>
          <Command.Input
            value={query}
            onValueChange={setQuery}
            placeholder="Search or go to\u2026"
            className="command-palette-input"
            autoFocus
          />
          <Command.List className="command-palette-list" aria-label="Suggestions">
            {results.length === 0 && (
              <Command.Empty className="command-palette-empty">
                No results found
              </Command.Empty>
            )}
            {results.some((r) => r.group === 'actions') && (
              <Command.Group heading="Actions" className="command-palette-group">
                {results
                  .filter((r): r is ActionItem => r.group === 'actions')
                  .map((item) => (
                    <Command.Item
                      key={item.id}
                      value={item.id}
                      onSelect={item.action}
                      className="command-palette-item"
                    >
                      <span className="command-palette-item-icon">{item.icon}</span>
                      <span className="command-palette-item-label">{item.label}</span>
                    </Command.Item>
                  ))}
              </Command.Group>
            )}
            {results.some((r) => r.group === 'notes') && (
              <Command.Group heading="Notes" className="command-palette-group">
                {results
                  .filter((r): r is NoteItem => r.group === 'notes')
                  .map((item) => (
                    <Command.Item
                      key={item.id}
                      value={item.id}
                      onSelect={() => { close(); navigate(`/editor/${item.id}`); }}
                      className="command-palette-item"
                    >
                      <span className="command-palette-item-icon"><FileText size={16} /></span>
                      <span className="command-palette-item-label">{item.title}</span>
                      <span className="command-palette-item-meta">{item.folder}</span>
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
