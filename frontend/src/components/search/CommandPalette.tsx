/**
 * CommandPalette — Global Cmd+K / Ctrl+K command palette.
 *
 * Features:
 *   - Opens on Cmd+K (Mac) or Ctrl+K (Windows/Linux) from anywhere in the app
 *   - Closes on Escape key
 *   - Fuzzy note search via Fuse.js over a cached note list
 *   - Built-in navigation actions: New Note, Go to Graph, Go to Search, Go to Settings
 *   - Keyboard navigation: Arrow keys, Enter to execute, Escape to dismiss
 *   - Uses cmdk (Command component) for accessible list management
 *
 * @see https://cmdk.paco.me
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import Fuse from "fuse.js";
import {
  FileText,
  GitBranch,
  Plus,
  Search,
  Settings,
  Zap,
} from "lucide-react";

/** Lightweight note stub used for palette search results. */
interface NoteStub {
  id: string;
  title: string;
  folder: string;
}

/** Static navigation action item. */
interface ActionItem {
  id: string;
  label: string;
  icon: React.ReactNode;
  action: () => void;
  group: "actions";
}

/** Note search result item. */
interface NoteItem {
  id: string;
  title: string;
  folder: string;
  group: "notes";
}

type PaletteItem = ActionItem | NoteItem;

/** Fetch vault note stubs for search index population. */
async function fetchNoteStubs(): Promise<NoteStub[]> {
  const base = import.meta.env.VITE_API_BASE_URL ?? "";
  try {
    const resp = await fetch(`${base}/api/v1/notes?limit=500`, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem("gnosis_token") ?? ""}`,
      },
    });
    if (!resp.ok) return [];
    const data = (await resp.json()) as { items?: NoteStub[] } | NoteStub[];
    return Array.isArray(data) ? data : data.items ?? [];
  } catch {
    return [];
  }
}

/** Create a new note via the API and navigate to the editor. */
async function createQuickNote(navigate: ReturnType<typeof useNavigate>) {
  const base = import.meta.env.VITE_API_BASE_URL ?? "";
  try {
    const resp = await fetch(`${base}/api/v1/notes`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${localStorage.getItem("gnosis_token") ?? ""}`,
      },
      body: JSON.stringify({
        title: "New Note",
        body: "",
        folder: "00-inbox",
        note_type: "fleeting",
      }),
    });
    if (resp.ok) {
      const note = (await resp.json()) as { id: string };
      navigate(`/editor/${note.id}`);
    }
  } catch {
    navigate("/editor/new");
  }
}

/** Props for CommandPalette component. */
interface CommandPaletteProps {
  /** Called when the palette should close (user pressed Escape or clicked backdrop). */
  onClose?: () => void;
}

/**
 * CommandPalette — Global search and navigation overlay.
 *
 * Can be imported as either a named or default import:
 *   import CommandPalette from './CommandPalette';
 *   import { CommandPalette } from './CommandPalette';
 */
export function CommandPalette({ onClose }: CommandPaletteProps = {}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [notes, setNotes] = useState<NoteStub[]>([]);
  const [results, setResults] = useState<PaletteItem[]>([]);
  const fuseRef = useRef<Fuse<NoteStub> | null>(null);
  const navigate = useNavigate();

  /** Load note stubs and build Fuse index on first open. */
  useEffect(() => {
    if (open && notes.length === 0) {
      fetchNoteStubs().then((stubs) => {
        setNotes(stubs);
        fuseRef.current = new Fuse(stubs, {
          keys: ["title", "folder"],
          threshold: 0.35,
          includeScore: true,
        });
      });
    }
  }, [open, notes.length]);

  /** Register Cmd+K / Ctrl+K global shortcut and Escape to close. */
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
        return;
      }
      if (e.key === "Escape") {
        setOpen((prev) => {
          if (prev) {
            // Reset query and notify parent when closing via Escape
            setQuery("");
            onClose?.();
            return false;
          }
          return prev;
        });
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  // onClose is stable (passed from parent), safe to include
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onClose]);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    onClose?.();
  }, [onClose]);

  /** Build static action items. */
  const actions: ActionItem[] = [
    {
      id: "new-note",
      label: "New Note in Inbox",
      icon: <Plus size={16} />,
      action: () => { close(); void createQuickNote(navigate); },
      group: "actions",
    },
    {
      id: "go-graph",
      label: "Open Knowledge Graph",
      icon: <GitBranch size={16} />,
      action: () => { close(); navigate("/graph"); },
      group: "actions",
    },
    {
      id: "go-search",
      label: "Search Vault",
      icon: <Search size={16} />,
      action: () => { close(); navigate("/search"); },
      group: "actions",
    },
    {
      id: "go-ai-chat",
      label: "Open AI Chat",
      icon: <Zap size={16} />,
      action: () => { close(); navigate("/ai-chat"); },
      group: "actions",
    },
    {
      id: "go-settings",
      label: "Settings",
      icon: <Settings size={16} />,
      action: () => { close(); navigate("/settings"); },
      group: "actions",
    },
  ];

  /** Update results when query changes. */
  useEffect(() => {
    if (!query.trim()) {
      setResults(actions);
      return;
    }
    const noteResults: NoteItem[] = fuseRef.current
      ? fuseRef.current.search(query).slice(0, 8).map(({ item }) => ({
          id: item.id,
          title: item.title,
          folder: item.folder,
          group: "notes" as const,
        }))
      : [];
    setResults([...actions.filter((a) =>
      a.label.toLowerCase().includes(query.toLowerCase())
    ), ...noteResults]);
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
            placeholder="Search notes or type a command…"
            className="command-palette-input"
            autoFocus
          />
          <Command.List className="command-palette-list">
            {results.length === 0 && (
              <Command.Empty className="command-palette-empty">
                No results found
              </Command.Empty>
            )}

            {/* Actions group */}
            {results.some((r) => r.group === "actions") && (
              <Command.Group heading="Actions" className="command-palette-group">
                {results
                  .filter((r): r is ActionItem => r.group === "actions")
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

            {/* Notes group */}
            {results.some((r) => r.group === "notes") && (
              <Command.Group heading="Notes" className="command-palette-group">
                {results
                  .filter((r): r is NoteItem => r.group === "notes")
                  .map((item) => (
                    <Command.Item
                      key={item.id}
                      value={item.id}
                      onSelect={() => {
                        close();
                        navigate(`/editor/${item.id}`);
                      }}
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

/** Allow both default and named imports. */
export default CommandPalette;
