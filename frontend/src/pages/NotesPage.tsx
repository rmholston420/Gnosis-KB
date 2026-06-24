import { useEffect, useState } from 'react';
import { Plus, Folder } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import NoteEditor from '../components/NoteEditor';
import api from '../services/api';
import type { Note, NoteListResponse } from '../types';

export default function NotesPage() {
  const { activeFolder, activeNoteId, setActiveNoteId } = useAppStore();
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string | number> = { page_size: 200 };
    if (activeFolder) params.folder = activeFolder;
    api
      .listNotes(params)
      .then((data) => {
        const resp = data as unknown as NoteListResponse;
        // listNotes returns { items, total, ... } — extract items
        setNotes(resp.items as unknown as Note[]);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [activeFolder]);

  const activeNote = notes.find((n) => n.id === activeNoteId) ?? null;

  async function handleNewNote() {
    const folder = activeFolder ?? '00-inbox';
    const created = (await api.createNote({
      title: 'Untitled',
      body: '',
      folder,
    })) as Note;
    setNotes((prev) => [created, ...prev]);
    setActiveNoteId(created.id);
  }

  // onSave signature matches NoteEditor: (body: string, title?: string) => Promise<void>
  async function handleSave(body: string, title?: string) {
    if (!activeNoteId) return;
    const updated = (await api.updateNote(activeNoteId, { body, title })) as Note;
    setNotes((prev) => prev.map((n) => (n.id === updated.id ? updated : n)));
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Note list */}
      <aside className="w-64 flex-shrink-0 border-r border-border flex flex-col bg-bg-secondary">
        <div className="h-10 flex items-center justify-between px-3 border-b border-border flex-shrink-0">
          <span className="text-xs font-semibold text-text-muted uppercase tracking-wider flex items-center gap-1.5">
            <Folder size={12} />
            {activeFolder ?? 'All Notes'}
          </span>
          <button
            onClick={handleNewNote}
            className="p-1 rounded hover:bg-bg-tertiary text-text-secondary hover:text-text-primary transition-colors"
            title="New note"
          >
            <Plus size={14} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto no-scrollbar">
          {loading ? (
            <div className="px-3 py-4 space-y-2">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="skeleton skeleton-text" />
              ))}
            </div>
          ) : notes.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-40 text-text-muted text-sm gap-2">
              <Folder size={24} className="text-text-faint" />
              <span>No notes here yet</span>
            </div>
          ) : (
            notes.map((note) => (
              <button
                key={note.id}
                onClick={() => setActiveNoteId(note.id)}
                className={`w-full text-left px-3 py-2.5 border-b border-border transition-colors ${
                  activeNoteId === note.id
                    ? 'bg-bg-elevated text-text-primary'
                    : 'text-text-secondary hover:bg-bg-tertiary hover:text-text-primary'
                }`}
              >
                <p className="text-sm font-medium truncate">{note.title}</p>
                <p className="text-xs text-text-muted truncate mt-0.5">
                  {note.folder ?? '\u2014'}
                </p>
              </button>
            ))
          )}
        </div>
      </aside>

      {/* Editor */}
      <div className="flex-1 overflow-hidden">
        {activeNote ? (
          <NoteEditor note={activeNote} onSave={handleSave} />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-text-muted gap-3">
            <BookOpenIcon />
            <p className="text-sm">Select a note or create a new one</p>
          </div>
        )}
      </div>
    </div>
  );
}

function BookOpenIcon() {
  return (
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-text-faint">
      <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
      <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
    </svg>
  );
}
